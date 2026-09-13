"""测试 task1 脚本的字典键是否能匹配16个词"""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))

# 直接从 task1_collocation 导入字典
from task1_collocation import COLLOCATIONS

target_words = [
    "好き", "とても", "そんな", "必ず", "少し",
    "立つ", "学ぶ", "なくなる", "やめる", "かまう",
    "取れる", "歌える", "きれい", "ありがとう", "決して", "いー"
]

print("Dict size:", len(COLLOCATIONS))
for w in target_words:
    found = w in COLLOCATIONS
    val = COLLOCATIONS.get(w, "-- NOT FOUND --")
    print(f"  {w}: {'FOUND' if found else 'MISSING'}  => {val[:30] if found else val}")
