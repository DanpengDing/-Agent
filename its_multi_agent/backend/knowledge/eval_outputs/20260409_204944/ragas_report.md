# RAGAS 评估报告

- 生成时间: 2026-04-09 20:58:33
- 爬取目录: `D:\BaiduNetdiskDownload\bj250716\its_multi_agent\backend\knowledge\data\crawl`
- 向量库目录: `D:\BaiduNetdiskDownload\bj250716\its_multi_agent\backend\knowledge\chroma_kb1`
- 已索引文档数: 747
- 评估样例数: 8
- 使用已有样本: True
- 启用事实正确性: True

## 指标汇总

| 指标 | 分数 |
| --- | ---: |
| context_recall | 0.6875 |
| faithfulness | 0.6717 |
| factual_correctness | 0.4800 |

## 逐条明细

| 来源文件 | 问题 | 召回标题 | context_recall | faithfulness | factual_correctness |
| --- | --- | --- | ---: | ---: | ---: |
| 0001-如何使用U盘安装Windows 7操作系统.md | 我想用U盘安装 Windows 7，应该怎么做？ | 如何使用U盘安装Windows 7操作系统 | 视频指导：Win主播带您安装Windows 10（U盘方式） | 1.0000 | 0.5333 | 0.4300 |
| 0004-开机之后无任何反应怎么办？.md | 电脑按开机键后完全没反应，主机灯也不亮，先检查什么？ | 开机之后无任何反应怎么办？ | 电脑经常死机 | 1.0000 | 1.0000 | 0.6700 |
| 0006-商用选件查询编号的方法.md | 商用键盘、鼠标或者U盘的编号一般去哪里看？ | 商用选件查询编号的方法 | 如何确认触控板的品牌（厂商） | 0.0000 | 0.0000 | 0.0000 |
| 0007-在 PowerPoint 2007 中无法输入中文怎么办？.md | PowerPoint 2007 里只能输英文和数字，不能输中文，怎么处理？ | 在 PowerPoint 2007 中无法输入中文怎么办？ | Windows XP如何添加、删除自带输入法 | 0.5000 | 0.9000 | 0.6000 |
| 0008-如何修改 Microsoft Word 的默认样式？.md | Word 的默认字体、字号和段落样式在哪里改？ | 如何修改 Microsoft Word 的默认样式？ | WinXP环境中，5-7号字体模糊的原因 | 1.0000 | 1.0000 | 0.5000 |
| 0009-禁止Office的上传中心和OneNote开机自启动的方法.md | 怎么禁止 Office 上传中心和 OneNote 开机自动启动？ | 禁止Office的上传中心和OneNote开机自启动的方法 | 我如何设置开机自动登录Lync？ | 1.0000 | 0.8333 | 0.5700 |
| 0011-Outlook为何没有已发送邮件的记录-.md | Outlook 发出去的邮件在“已发送邮件”里看不到，应该怎么设置？ | Outlook为何没有已发送邮件的记录- | 将Outlook设为Mac默认程序后为何仍弹出Apple Mail？ | 1.0000 | 0.8571 | 0.6700 |
| 0014-Internet Explorer 下载完成后怎么不弹出提示框？.md | IE 下载完成后不再弹出提示框了，怎么恢复？ | Internet Explorer 下载完成后怎么不弹出提示框？ | Internet Explorer版本升级说明 | 0.0000 | 0.2500 | 0.4000 |