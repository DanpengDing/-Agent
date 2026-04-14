EVAL_CASES = [
    {
        "source_file": "0001-如何使用U盘安装Windows 7操作系统.md",
        "question": "我想用U盘安装 Windows 7，应该怎么做？",
        "reference": "可以用 UltraISO 制作启动U盘：先打开 Windows 7 的 ISO 镜像，再选择“启动光盘”里的“写入硬盘映像”，确认目标U盘后点击“写入”。这个操作会格式化U盘，需要提前备份数据。",
    },
    {
        "source_file": "0004-开机之后无任何反应怎么办？.md",
        "question": "电脑按开机键后完全没反应，主机灯也不亮，先检查什么？",
        "reference": "先检查主机接口和插线板上的电源线是否连接正常；然后断开电源线，多按几次电源开关释放静电，再重新接回电源线后开机重试。",
    },
    {
        "source_file": "0006-商用选件查询编号的方法.md",
        "question": "商用键盘、鼠标或者U盘的编号一般去哪里看？",
        "reference": "常见位置包括设备本体上的条码或 S/N 后面的 15 位号码、包装盒正面标签上的序列号，以及保修卡或用户指南附表中的产品条码序列号。",
    },
    {
        "source_file": "0007-在 PowerPoint 2007 中无法输入中文怎么办？.md",
        "question": "PowerPoint 2007 里只能输英文和数字，不能输中文，怎么处理？",
        "reference": "先到“区域和语言选项”里的“文字服务和输入语言”检查是否误勾选了“关闭高级文字服务”，如果勾选了就取消。若该服务总是自动关闭，可补上 ctfmon.exe 并在注册表的 Run 项中添加启动项。",
    },
    {
        "source_file": "0008-如何修改 Microsoft Word 的默认样式？.md",
        "question": "Word 的默认字体、字号和段落样式在哪里改？",
        "reference": "在 Word 的“开始”选项卡打开“样式”窗口，再点“管理样式”，切到“设置默认值”后修改字体、字号、段落位置和间距并保存。若想恢复系统默认样式，可以删除 `%appdata%\\microsoft\\templates` 下的 `Normal.dotm`。",
    },
    {
        "source_file": "0009-禁止Office的上传中心和OneNote开机自启动的方法.md",
        "question": "怎么禁止 Office 上传中心和 OneNote 开机自动启动？",
        "reference": "可以运行 `msconfig`，在“启动”选项卡中取消勾选 Microsoft OneNote 和 Microsoft Office 2010 对应的启动项，保存后重启电脑。",
    },
    {
        "source_file": "0011-Outlook为何没有已发送邮件的记录-.md",
        "question": "Outlook 发出去的邮件在“已发送邮件”里看不到，应该怎么设置？",
        "reference": "进入 Outlook 的邮件选项，勾选“在已发送邮件文件夹中保留邮件副本”。Outlook 2010 在“文件-选项-邮件”里设置，Outlook 2007 在“工具-选项-电子邮件选项”里设置。",
    },
    {
        "source_file": "0014-Internet Explorer 下载完成后怎么不弹出提示框？.md",
        "question": "IE 下载完成后不再弹出提示框了，怎么恢复？",
        "reference": "打开 Internet Explorer 的“Internet 选项”，切到“高级”选项卡，找到并勾选“下载完成后发出通知”，保存后即可恢复提示。",
    },
]
