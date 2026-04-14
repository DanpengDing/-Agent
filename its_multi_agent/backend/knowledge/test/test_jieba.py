# encoding=utf-8
import jieba

seg_list = jieba.cut("我来到北京清华大学", cut_all=True)
print("Full Mode: " + "/ ".join(seg_list))  # 全模式

seg_list = jieba.cut("我来到北京清华大学", cut_all=False)
print("Default Mode: " + "/ ".join(seg_list))  # 默认模式



# --------------------------------------------------------------------------
#

step1=jieba.lcut("如何学习Python") # 如何 学习 Python
print(step1)
seg_set1=set(step1)

step2=jieba.lcut("如何学习Java")  # 如何 Java 学习

seg_set2=set(step2)


print(seg_set1)
print(seg_set2)
