# TT-MAKER

เปลี่ยนเอกสารเป็นคลิป TikTok สไตล์ pixel 16-bit พร้อมเสียงพากย์ไทย (ฟรีทั้งหมด)

```bash
pip install -r requirements.txt   # ต้องมี ffmpeg ด้วย
python3 render.py series/democratic-socialism/script.json   # -> out/democratic-socialism/ep*.mp4 + ep*.txt
python3 test_render.py
```

วิธีใช้กับ Claude Code และกติกาการเขียน `script.json` อยู่ใน [CLAUDE.md](CLAUDE.md)
