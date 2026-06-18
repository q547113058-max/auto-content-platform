"""生成测试用 .xlsx 知识库文件 — 模拟竖表布局"""
from openpyxl import Workbook

wb = Workbook()
ws = wb.active
ws.title = "产品知识库"

# 竖表布局：A列字段名，B列值
data = [
    ("产品名称", "水光焕颜面膜"),
    ("品类", "护肤品 - 面膜"),
    ("参考价格", "199元/5片装"),
    ("核心成分", "透明质酸、海藻糖、烟酰胺、神经酰胺、积雪草提取物"),
    ("功效宣称", "深层补水、提亮肤色、修复屏障、舒缓敏感"),
    ("目标人群", "25-35岁干性/混干肌肤，敏感肌适用，经常熬夜的都市白领"),
    ("行业背景", "2024年面膜市场突破600亿，贴片面膜占比超70%。功效型面膜增速领先，补水修护是最大细分品类。消费者偏好'成分精简、效果可验证'的产品，神经酰胺和积雪草成为年度热门成分。"),
]

for row_data in data:
    ws.append(row_data)

# 调整列宽
ws.column_dimensions['A'].width = 18
ws.column_dimensions['B'].width = 60

wb.save("test_knowledge.xlsx")
print("Test xlsx created: test_knowledge.xlsx")
