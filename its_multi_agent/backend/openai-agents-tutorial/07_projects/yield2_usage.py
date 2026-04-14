# 模拟一个巨大的数据源（列表）
raw_data_source = ["Row 1", "Row 2", "   ", "Row 4", "Row 5"]


def process_large_file(data):
    for line in data:
        # 模拟复杂的清洗逻辑
        cleaned_line = line.strip()
        if not cleaned_line:
            continue  # 跳过空行

        # 假设这里还有耗时的数据库查询操作...

        # 处理完一行，立刻交出去，不要积压在内存里
        yield f"Processed: {cleaned_line}"


# 使用生成器
processor = process_large_file(raw_data_source)

# for 循环会自动调用 next() 直到没有数据
for item in processor:
    print(f"获得结果 -> {item}")