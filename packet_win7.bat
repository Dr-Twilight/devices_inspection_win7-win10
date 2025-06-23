@echo off
cd /d %~dp0

echo 开始多行打包...
pyinstaller --clean -F devices_inspection_win7.py ^
--hidden-import=pandas ^
--hidden-import=openpyxl ^
--hidden-import=netmiko ^
--hidden-import=paramiko ^
--hidden-import=cryptography ^
--hidden-import=cryptography.hazmat.bindings._rust ^
--hidden-import=bcrypt ^
--hidden-import=msoffcrypto.tool ^
--hidden-import=idna ^
--hidden-import=encodings.idna

echo.
echo 如不成功请手动使用以下单行命令（复制后移除echo再运行）：
echo pyinstaller --clean -F devices_inspection_win7.py --hidden-import=pandas --hidden-import=openpyxl --hidden-import=netmiko --hidden-import=paramiko --hidden-import=cryptography --hidden-import=cryptography.hazmat.bindings._rust --hidden-import=bcrypt --hidden-import=msoffcrypto.tool --hidden-import=idna --hidden-import=encodings.idna

pause
