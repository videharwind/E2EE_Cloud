from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from supabase import create_client, Client
from dotenv import load_dotenv
from io import BytesIO
import os
import uuid
import re

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# Supabase config
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME = os.getenv("BUCKET_NAME")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ---------------- AUTH ROUTES ---------------- #
@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("storage"))
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        try:
            result = supabase.auth.sign_up({"email": email, "password": password})
            if result.user:
                flash("Signup successful! Please log in.", "success")
                return redirect(url_for("login"))
        except Exception as e:
            flash(str(e), "danger")
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        try:
            user = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if user.user:
                session["user"] = {"id": user.user.id, "email": user.user.email}
                return redirect(url_for("storage"))
            else:
                flash("Invalid credentials", "danger")
        except Exception as e:
            flash(str(e), "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))


# ---------------- STORAGE ROUTES ---------------- #
@app.route("/storage")
def storage():
    if "user" not in session:
        return redirect(url_for("login"))

    user_email = session["user"]["email"]
    safe_email = re.sub(r'[^a-zA-Z0-9_-]', '_', user_email)
    current_path = request.args.get("path", "").strip("/")
    base_path = f"{safe_email}/{current_path}".rstrip("/")

    try:
        response = supabase.storage.from_(BUCKET_NAME).list(
            path=base_path if base_path else safe_email,
            options={
                "limit": 100,
                "offset": 0,
                "sortBy": {"column": "name", "order": "asc"}
            }
        )

        folders, files = [], []
        for item in response:
            name = item["name"]
            if item["metadata"] is None:
                folders.append(name)
            else:
                # Check if this file has an original name saved as metadata
                display_name = name
                if "_" in name and len(name.split("_", 1)) == 2:
                    display_name = name.split("_", 1)[1]
                files.append({
                    "real_name": name,
                    "display_name": display_name
                })
    except Exception as e:
        flash(f"Error listing files: {e}", "danger")
        folders, files = [], []
        \

    parent_path = "/".join(current_path.split("/")[:-1]) if "/" in current_path else ""

    return render_template(
        "dashboard.html",
        user_email=user_email,
        files=files,
        folders=folders,
        current_path=current_path,
        parent_path=parent_path
    )




@app.route("/upload", methods=["POST"])
def upload():
    if "user" not in session:
        return redirect(url_for("login"))

    user_email = session["user"]["email"]
    file = request.files.get("file")
    current_path = request.form.get("current_path", "").strip("/")

    if not file or file.filename == '':
        flash("No file selected.", "warning")
        return redirect(url_for("storage", path=current_path))

    safe_email = re.sub(r'[^a-zA-Z0-9_-]', '_', user_email)
    clean_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', file.filename)
    folder_prefix = f"{safe_email}/{current_path}" if current_path else safe_email
    unique_name = f"{folder_prefix}/{uuid.uuid4()}_{clean_filename}"

    try:
        file_data = file.read()
        content_type = file.content_type or "application/octet-stream"
        supabase.storage.from_(BUCKET_NAME).upload(
            path=unique_name,
            file=file_data,
            file_options={"content-type": content_type}
        )
        flash("File uploaded successfully!", "success")
    except Exception as e:
        flash(f"Upload failed: {e}", "danger")

    return redirect(url_for("storage", path=current_path))


@app.route("/create_folder", methods=["POST"])
def create_folder():
    if "user" not in session:
        return redirect(url_for("login"))

    folder_name = request.form.get("folder_name")
    current_path = request.form.get("current_path", "").strip("/")
    user_email = session["user"]["email"]

    if not folder_name:
        flash("Folder name cannot be empty.", "warning")
        return redirect(url_for("storage", path=current_path))

    safe_email = re.sub(r'[^a-zA-Z0-9_-]', '_', user_email)
    base_prefix = f"{safe_email}/{current_path}".rstrip("/")
    folder_path = f"{base_prefix}/{folder_name}/.keep" if base_prefix else f"{safe_email}/{folder_name}/.keep"

    try:
        supabase.storage.from_(BUCKET_NAME).upload(path=folder_path, file=b"")
        flash("Folder created successfully!", "success")
    except Exception as e:
        flash(f"Error creating folder: {e}", "danger")

    return redirect(url_for("storage", path=current_path))

@app.route("/download/<path:filename>")
def download(filename):
    if "user" not in session:
        return redirect(url_for("login"))

    user_email = session["user"]["email"]
    safe_email = re.sub(r'[^a-zA-Z0-9_-]', '_', user_email)
    full_path = f"{safe_email}/{filename}"

    try:
        file_bytes = supabase.storage.from_(BUCKET_NAME).download(path=full_path)
        return send_file(BytesIO(file_bytes), download_name=filename, as_attachment=True)
    except Exception as e:
        flash(f"Download failed: {e}", "danger")
        return redirect(url_for("storage"))


@app.route("/delete/<path:filename>")
def delete(filename):
    if "user" not in session:
        return redirect(url_for("login"))

    user_email = session["user"]["email"]
    safe_email = re.sub(r'[^a-zA-Z0-9_-]', '_', user_email)
    file_path = f"{safe_email}/{filename}"

    try:
        supabase.storage.from_(BUCKET_NAME).remove([file_path])
        flash(f"File '{filename}' deleted successfully!", "success")
    except Exception as e:
        flash(f"Deletion failed: {e}", "danger")

    return redirect(url_for("storage"))


if __name__ == "__main__":
    app.run(debug=True)
