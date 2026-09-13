import zipfile, re, sys
sys.stdout.reconfigure(encoding="utf-8")
with zipfile.ZipFile("N2高频词训练系统_产品设计说明书_v3.docx", "r") as z:
    with z.open("word/document.xml") as f:
        content = f.read().decode("utf-8")
        text = re.sub(r"<[^>]+>", "", content)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        print(text[:12000])
