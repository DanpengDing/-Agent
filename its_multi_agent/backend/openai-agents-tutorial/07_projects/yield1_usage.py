def simple_generator():
    print("--- 准备生成第 1 个数据 ---")
    yield 1
    print("--- 准备生成第 2 个数据 ---")
    yield 2
    print("--- 准备生成第 3 个数据 ---")
    yield 3

def  abc():
    return 1+1
# 1. 创建生成器对象（此时函数内部的代码**一行都不会执行**）
gen = simple_generator()
# # 2. 手动索要数据
print(f"拿到数据: {next(gen)}") # 执行到第一个 yield 1 暂停
print(f"拿到数据: {next(gen)}") # 从上次暂停处继续，执行到 yield 2 暂停
print(f"拿到数据: {next(gen)}") # 从上次暂停处继续，执行到 yield 3 暂停
print(f"拿到数据: {next(gen)}") # 从上次暂停处继续，执行到 yield 3 暂停
#
# # print(next(gen)) # 如果再运行这行，会报错 StopIteration，因为没数据了
