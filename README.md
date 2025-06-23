📘 README.md

# Devices Inspection Tool

一个基于 Python 和 Netmiko 的网络设备自动巡检工具，支持 Excel 配置输入、SSH 并发连接、加密文件解析、命令回显处理与日志记录，适配 Win7/Win10 环境，支持 PyInstaller 一键打包为独立可执行程序。

---

## 🧩 功能特点

- ✅ 支持 Excel 加密文件读取（基于 `msoffcrypto`）
- ✅ 自动识别设备类型并执行对应命令
- ✅ 并发线程池执行巡检任务，支持守护线程防止僵尸进程残留
- ✅ 区分无回显命令（如 `sys`、`enable`），使用 `send_command_timing` 提升兼容性
- ✅ 控制台与日志双输出，集中记录 `01log.log` 错误信息
- ✅ 自动生成分设备日志：`logs/日期/host.log`
- ✅ 支持 Windows 系统 PyInstaller 打包（内含打包脚本）

---

## 🛠 使用说明

### 1. 准备环境

建议使用 Python 3.10+，安装依赖：
```python
pip install -r requirements.txt
```
### 2. 准备 info 文件
准备 Excel 文件 info.xlsx，含两个 Sheet：

Sheet1：设备信息（字段示例：device_type, host, ip, username, password, secret）

Sheet2：巡检命令列表（以设备类型为列名）

支持加密 Excel 文件，运行时将提示输入密码。

📘 支持设备类型对照表（Netmiko）
在 info.xlsx 中的 device_type 字段，请参考以下表格设置设备类型：

| 品牌 / 设备                | device\_type 值      | 说明                    |
| ---------------------- | ------------------- | --------------------- |
| **Cisco IOS 路由器/交换机**  | `cisco_ios`         | 常用                    |
| Cisco IOS-XE           | `cisco_xe`          | ISR4K / Catalyst 9000 |
| Cisco ASA 防火墙          | `cisco_asa`         | 需启用 SSH               |
| Cisco NX-OS            | `cisco_nxos`        | Nexus 系列              |
| Cisco IOS-XR           | `cisco_xr`          | 高端路由器（如 ASR）          |
| Cisco SG300            | `cisco_s300`        | Web 管理交换机             |
| **华为 Huawei**          | `huawei`            | S/CE 系列，SSH 登录        |
| **华三 H3C**             | `hp_comware`        | 推荐用于 Comware 系列       |
| **Juniper**            | `juniper`           | JunOS 系统设备            |
| **Arista EOS**         | `arista_eos`        | Arista 交换机            |
| **Fortinet**           | `fortinet`          | FortiGate 防火墙         |
| **HP ProCurve**        | `hp_procurve`       | 老款 HPE 网络设备           |
| **Dell PowerConnect**  | `dell_powerconnect` | 接入层常用                 |
| **Mikrotik RouterOS**  | `mikrotik_routeros` | SSH 接入                |
| **F5 BIG-IP**          | `f5_ltm`            | 需启用 SSH               |
| **Checkpoint Gaia**    | `checkpoint_gaia`   | 防火墙系统                 |
| **Palo Alto PAN-OS**   | `paloalto_panos`    | 防火墙设备                 |
| **Brocade / Ruckus**   | `brocade_fastiron`  | ICX 系列交换机             |
| **Ciena SAOS**         | `ciena_saos`        | 光传输设备                 |
| **Ubiquiti EdgeOS**    | `ubiquiti_edge`     | EdgeRouter 路由器        |
| **Alcatel OmniSwitch** | `alcatel_aos`       | AOS 系统设备              |

### 3. 运行脚本
```python
python devices_inspection_win7.py
```
程序将提示输入 info 文件名和是否显示实时命令回显，默认使用 info.xlsx 和不显示回显。

### 4. 查看日志
错误信息：logs/01log.log

单设备日志：logs/2025.06.23/192.168.1.1.log（按日期存储）

🧵 打包为 EXE（可选）
确保已安装打包依赖：
请确保使用 Python 3.8–3.11 环境，并安装以下依赖：
```python
pip install -r requirements_win7.txt
```
运行内置打包脚本：
```python
packet_win7.bat
```
打包命令：
```python
pyinstaller --clean -F devices_inspection_win7.py --hidden-import=pandas --hidden-import=openpyxl --hidden-import=netmiko --hidden-import=paramiko --hidden-import=cryptography --hidden-import=cryptography.hazmat.bindings._rust --hidden-import=bcrypt --hidden-import=msoffcrypto.tool --hidden-import=idna --hidden-import=encodings.idna
```
输出独立的 devices_inspection_win7.exe 可在无 Python 环境的机器上运行。

📂 项目根目录
```python
├── devices_inspection_win7.py       # 主程序
├── requirements_win7.txt            # 所需依赖列表
├── info.xlsx                        # 设备与命令配置文件（支持加密）
├── packet_win7.bat                  # Windows 一键打包脚本
├── logs/                            # 日志目录
│   ├── 01log.log                    # 主日志（记录异常和流程信息）
│   └── YYYY.MM.DD/                 # 每次巡检按日期分目录保存
│       └── <host>.log              # 每台设备的详细巡检日志
```


🧾 致谢与协议
本项目基于：

原始项目：@icefire-ken

原项目协议：MIT License（见 LICENSE）

在原有基础上进行增强与扩展，感谢原作者的高质量开源贡献 🙏


## 以下为原readme.md


# 简介

- 作为网络工程师工作中经常遇到需要对网络设备进行巡检的情况，此前都是用SecureCRT软件开启记录Log Session，依次登录每台设备，依次输入命令收集巡检信息。
  
- 现在利用Python实现自动登录网络设备，自动输入命令收集巡检信息；并且使用多线程技术，缩减巡检时间。
  
- 在登录出现故障时，能够记录Log提醒工程师，待排查故障后可再次进行巡检。

- 执行巡检能够在.py脚本所在目录下生成当前日期的巡检信息存放目录，其中每台设备的巡检信息文件以设备名称命名。

- .py脚本已经封装为.exe程序，配合info文件可以方便的在没有Python环境的PC上使用。（可在Releases中下载）

# 使用方法

## Step-1、执行准备

- 准备info.xlsx文件，与.exe程序或.py脚本存放于同一目录，文件里应存有需要巡检设备的登录信息和巡检命令。

info文件内sheet1存放被巡检网络设备的登录信息，如下：

![sheet1.png](https://github.com/icefire-ken/devices_inspection/blob/main/images/sheet1.png?raw=true)

info文件内sheet2存放用于网络设备巡检输入的命令，如下：

![sheet2.png](https://github.com/icefire-ken/devices_inspection/blob/main/images/sheet2.png?raw=true)

## Step-2、exe程序执行（Step-2与Step-3任选其一）

- 在Releases中下载.exe程序。
- 运行.exe程序，开始巡检。

![exe.png](https://github.com/icefire-ken/devices_inspection/blob/main/images/exe.png?raw=true)

## Step-3、py脚本执行（Step-2与Step-3任选其一）

- py脚本执行需要先安装python环境与依赖的第三方库，利用requirements.txt文件，使用下面的命令安装依赖的第三方库。

```python
pip install -r requirements.txt
```

- 在脚本文件目录下，使用下面的命令运行脚本，开始巡检。

```python
python devices_inspection.py
```

# 关于info文件中的Secret密码！

- 如果人工登录设备没有要求输入Enable Password，info文件中的Secret字段为空（无需填写）。
- ~~A10设备默认是没有Enable Password的，但进入Enable模式时，仍然会提示要求输入Enable Password，人工操作时可以直接Enter进入；使用脚本时需要在info文件的Secret字段中填入空格即可。~~
  - 不再需要，2024.02.02更新解决。

# 为info文件添加需要的设备类型

## Step-1、首先确认Netmiko支持的设备类型

- 访问[Netmiko PLATFORMS](https://github.com/ktbyers/netmiko/blob/develop/PLATFORMS.md)，查看支持的设备类型。

## Step-2、添加设备类型进info文件

- 在info文件内sheet1的Device Type列，添加需要的设备类型，并填写正确的登录信息。
![add_device_type.png](https://github.com/icefire-ken/devices_inspection/blob/main/images/add_device_type.png?raw=true)
- 在info文件内sheet2添加该设备类型对应的巡检命令。
![add_command.png](https://github.com/icefire-ken/devices_inspection/blob/main/images/add_command.png?raw=true)

# 关于使用Telnet方式登录设备

- Netmiko使用deivce_type后缀的方式来识别使用Telnet方式登录的设备，比如：cisco_ios_telnet，有此后缀的设备Netmiko会自动使用Telnet方式登录。
- 但Netmiko目前支持Telnet方式登录的设备类型有限，具体可参考[Netmiko PLATFORMS](https://github.com/ktbyers/netmiko/blob/develop/PLATFORMS.md)官方说明。
- 使用Telnet方式巡检时，在info文件内sheet1的deivce_type列中，添加带有Telnet后缀标识的device_type，如：cisco_ios_telnet。（方法与**为info文件添加需要的设备类型**相同）
- 相应的，sheet2中也需要使用带有Telnet后缀的device_type，如：cisco_ios_telnet，来标识来用巡检此类型设备的巡检命令。（方法与**为info文件添加需要的设备类型**相同）

# 关于加密info文件的方式

- 想要为info文件加密，请参照下面的方法。
- 依次点击文件-信息-保护工作薄-用密码进行加密。
- 输入密码，并再次确认密码即可。。

<img src="https://github.com/icefire-ken/devices_inspection/blob/main/images/encrypt_1.png" width="400" />

<img src="https://github.com/icefire-ken/devices_inspection/blob/main/images/encrypt_2.png" width="400" />

<img src="https://github.com/icefire-ken/devices_inspection/blob/main/images/encrypt_3.png" width="400" />

# 更新日志

详见[UPDATE.md](https://github.com/icefire-ken/devices_inspection/blob/main/UPDATE.md)。
