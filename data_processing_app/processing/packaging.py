import os, sys, shutil, subprocess, secrets, string

class ZipEncryptor:
    def find_7zip(self):
        bundle = getattr(sys, "_MEIPASS", None)
        if bundle:
            for n in ("7z","7z.exe"):
                p = os.path.join(bundle, n)
                if os.path.isfile(p):
                    return p

        for c in [
            "7z","7za",
            r"C:\Program Files\7-Zip\7z.exe",
            r"C:\Program Files (x86)\7-Zip\7z.exe"
        ]:
            p = shutil.which(c) or (c if os.path.isfile(c) else None)
            if p:
                return p
        return None

    def generate_password(self, length=16):
        chars = string.ascii_letters + string.digits + "-_@#$^!=+"
        return "".join(secrets.choice(chars) for _ in range(length))

    def create_zip(self, folder, out_file, password):
        seven = self.find_7zip()
        if not seven:
            raise FileNotFoundError("7-Zip not found")

        cmd = [
            seven,
            "a",
            "-tzip",
            out_file,
            os.path.join(folder, "*"),
            f"-p{password}",
            "-mem=ZipCrypto",
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
        except OSError as e:
            if getattr(e, "winerror", None) == 740:
                raise PermissionError("Permission Error") from None
            if getattr(e, "winerror", None) == 5:
                raise PermissionError("Permission Error") from None
            raise

        if res.returncode != 0:
            msg = (res.stderr or res.stdout or "").strip()
            lower = msg.lower()
            if ("access is denied" in lower) or ("permission" in lower) or ("denied" in lower):
                raise PermissionError("Permission Error")
            raise RuntimeError(msg or "ZIP creation failed")