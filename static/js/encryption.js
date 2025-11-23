const salt =  window.crypto.getRandomValues(new Uint8Array(16));

const myform = document.getElementById("myFormId");

myform.addEventListener('submit',async function(event){
]
    const formData = new FormData(myform);

    const password = document.getElementById("password").value;
    try{
        const baseKey = await window.crypto.subtle.importKey(
            "raw",
            new TextEncoder().encode(password),
            { name: "PBKDF2" },
            false,
            ["deriveKey"],
        );
        console.log("base key successfully created")
        const derivedKey = window.crypto.subtle.deriveKey(
            {
                name: "PBKDF2",
                salt,
                iterations: 600000,
                hash: "SHA-256",
            },
            baseKey,
            { name: "AES-GCM", length: 256 },
            true,
            ["encrypt", "decrypt"],
        );
    } catch(error){
        console.error("error: ",error);
    }
});
