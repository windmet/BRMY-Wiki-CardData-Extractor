from PIL import Image
import os

# 你的高保真透明小鸟 PNG 文件名
png_name = "avatar.png" 

if not os.path.exists(png_name):
    print(f"[!] 找不到文件: {png_name}，请确认它在当前文件夹下！")
else:
    img = Image.open(png_name)
    # 打包 Windows 规范的全部 6 种尺寸
    img.save(
        "logo.ico", 
        format="ICO", 
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    )
    print("[√] 高清、多规格的 logo.ico 生成成功！")