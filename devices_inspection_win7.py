#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

# ==============================================
# 系统模块导入区
# ==============================================
import os
import sys
import time
import getpass
import threading
from io import BytesIO
import logging  # 引入日志模块

# ==============================================
# 第三方库导入区
# ==============================================
import msoffcrypto  # Excel文件解密库
import pandas as pd  # 数据处理库
from netmiko import ConnectHandler  # 网络设备连接库
from netmiko import exceptions  # Netmiko异常处理

# ==============================================
# 编码修复区（解决特定环境下的idna编码问题）
# ==============================================
import idna
import codecs
import encodings.idna
# 注册自定义编码处理器，修复idna编码冲突
codecs.register(lambda name: encodings.idna.getregentry() if name == 'idna' else None)


# ==============================================
# 自定义异常定义
# ==============================================
class PasswordRequiredError(Exception):
    """
    文件受密码保护时抛出的异常
    用于明确区分密码缺失与其他文件读取错误
    """
    pass


# ==============================================
# 全局配置与路径处理
# ==============================================
# 获取用户输入的info文件名（默认为info.xlsx）
FILENAME = input(f"\n请输入info文件名（默认为 info.xlsx）：") or "info.xlsx"

INSPECTION_TASK_TIMEOUT = 200   # 每台设备最大巡检总时长（秒）
INSPECTION_CMD_TIMEOUT = 10     # 单条命令最大超时（秒）

# ==============================================
# 路径与日志配置模块
# ==============================================
# 获取脚本所在目录的绝对路径
def get_base_dir():
    """
    动态获取脚本执行目录
    - 打包为exe时:返回exe所在目录
    - 脚本运行时：返回脚本文件所在目录
    """
    if getattr(sys, 'frozen', False):  # 判断是否为PyInstaller打包环境
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

# 基础路径配置
SCRIPT_DIR = get_base_dir()  # 脚本根目录
LOG_DIR = os.path.join(SCRIPT_DIR, 'logs')  # 日志存储目录
os.makedirs(LOG_DIR, exist_ok=True)  # 确保日志目录存在，不存在则创建

# 信息文件路径
INFO_PATH = os.path.join(SCRIPT_DIR, FILENAME)  # 拼接info文件完整路径

# 时间戳配置（全局统一时间基准）
RUN_START_TIME = time.localtime()  # 程序启动时的本地时间
LOCAL_TIME = time.strftime('%Y.%m.%d', RUN_START_TIME)  # 格式化日期（用于日志命名）



# 线程安全配置
LOCK = threading.Lock()  # 全局线程锁，防止多线程输出混乱


# ==============================================
# 日志处理函数
# ==============================================
# 统一日志记录函数（同时输出到控制台和01log.log）
# 日志配置
LOG_FILE = os.path.join(LOG_DIR, '01log.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 兼容原有 log_message 调用方式
def log_message(msg: str):
    with LOCK:
        logging.info(msg)

# 定义日志路径
LOG_DATE_DIR = os.path.join(LOG_DIR, LOCAL_TIME)  # logs/2025.06.09/
os.makedirs(LOG_DATE_DIR, exist_ok=True)


# ==============================================
# 数据读取模块
# ==============================================
from typing import List, Dict, Tuple

# 判断info文件是否被加密，使用不同的读取方式
def read_info() -> Tuple[List[Dict], Dict[str, List]]:
    if is_encrypted(INFO_PATH):
        return read_encrypted_file(INFO_PATH)  # 读取被加密info文件
    else:
        return read_unencrypted_file(INFO_PATH)  # 读取未加密info文件


# 检测info文件是否被加密
def is_encrypted(info_file: str) -> bool:
    try:
        with open(info_file, "rb") as f:
            return msoffcrypto.OfficeFile(f).is_encrypted()  # 检测info文件是否被加密
    except Exception:
        return False


# 读取被加密info文件
def read_encrypted_file(info_file: str, max_retry: int = 3) -> pd.DataFrame:
    retry_count = 0  # 初始化重试计数器，用于记录用户尝试输入密码的次数
    while retry_count < max_retry:  # 当重试次数小于最大允许重试次数时，继续循环
        try:
            password = getpass.getpass("\n info文件被加密，请输入密码：") or None  # 提示用户输入密码，隐式输入。如果用户直接按Enter键，password将为None
            if not password:  # 如果用户没有输入密码
                raise PasswordRequiredError("文件受密码保护，必须提供密码！")  # 抛出自定义异常，提示用户必须提供密码

            # 解密文件
            decrypted_data = BytesIO()  # 创建一个BytesIO对象，用于在内存中存储解密后的文件内容
            # BytesIO是一个内存中的二进制流，可以像文件一样进行读写操作
            with open(info_file, "rb") as f:  # 以二进制只读模式打开加密的info文件
                office_file = msoffcrypto.OfficeFile(f)  # 使用msoffcrypto库创建一个OfficeFile对象，表示加密的Office文件
                office_file.load_key(password=password)  # 使用用户提供的密码加载解密密钥
                office_file.decrypt(decrypted_data)  # 解密文件内容，并将解密后的数据写入decrypted_data对象中
            decrypted_data.seek(0)  # 将decrypted_data的指针重置到起始位置，以便后续读取操作
            # 由于解密后的数据已经写入decrypted_data，需要将指针重置到开头，以便后续读取

            # 读取解密后的文件
            devices_dataframe = pd.read_excel(decrypted_data, sheet_name=0, dtype=str, keep_default_na=False)
            cmds_dataframe = pd.read_excel(decrypted_data, sheet_name=1, dtype=str)

        except FileNotFoundError:  # 如果没有配置info文件或info文件名错误
            print(f'\n没有找到info文件！\n')  # 提示用户没有找到info文件或info文件名错误
            input('输入Enter退出！')  # 提示用户按Enter键退出
            sys.exit(1)  # 异常退出
        except ValueError:  # 捕获异常信息
            print(f'\ninfo文件缺失子表格信息！\n')  # 代表info文件缺失子表格信息
            input('输入Enter退出！')  # 提示用户按Enter键退出
            sys.exit(1)  # 异常退出
        except (msoffcrypto.exceptions.InvalidKeyError, PasswordRequiredError) as e:
            retry_count += 1
            if retry_count < max_retry:
                print(f"\n密码错误，请重新输入！（剩余尝试次数：{max_retry - retry_count}）")
            else:
                input("\n超过最大尝试次数，输入Enter退出！")
                sys.exit(1)
        except Exception as e:
            print(f"\n解密失败：{str(e)}")
            sys.exit(1)
        else:
            devices_dict = devices_dataframe.to_dict('records')  # 将DataFrame转换成字典
            # "records"参数规定外层为列表，内层以列标题为key，以此列的行内容为value的字典
            # 若有多列，代表字典内有多个key:value对；若有多行，每行为一个字典

            cmds_dict = cmds_dataframe.to_dict('list')  # 将DataFrame转换成字典
            # "list"参数规定外层为字典，列标题为key，列下所有行内容以list形式为value的字典
            # 若有多列，代表字典内有多个key:value对

            return devices_dict, cmds_dict


# 读取未加密info文件
def read_unencrypted_file(info_file: str) -> pd.DataFrame:
    try:
        devices_dataframe = pd.read_excel(info_file, sheet_name=0, dtype=str, keep_default_na=False)
        cmds_dataframe = pd.read_excel(info_file, sheet_name=1, dtype=str)
    except FileNotFoundError:  # 如果没有配置info文件或info文件名错误
        print(f'\n没有找到info文件！\n')  # 代表没有找到info文件或info文件名错误
        input('输入Enter退出！')  # 提示用户按Enter键退出
        sys.exit(1)  # 异常退出
    except ValueError:  # 捕获异常信息
        print(f'\ninfo文件缺失子表格信息！\n')  # 代表info文件缺失子表格信息
        input('输入Enter退出！')  # 提示用户按Enter键退出
        sys.exit(1)  # 异常退出
    else:
        devices_dict = devices_dataframe.to_dict('records')  #将DataFrame转换成字典
        # "records"参数规定外层为列表，内层以列标题为key，以此列的行内容为value的字典
        # 若有多列，代表字典内有多个key:value对；若有多行，每行为一个字典

        cmds_dict = cmds_dataframe.to_dict('list')  # 将DataFrame转换成字典
        # "list"参数规定外层为字典，列标题为key，列下所有行内容以list形式为value的字典
        # 若有多列，代表字典内有多个key:value对

        return devices_dict, cmds_dict


# 巡检
# 巡检主函数
def inspection(login_info, cmds_dict, show_output):
    # 使用传入的设备登录信息和巡检命令登录设备并执行巡检
    # 若登录异常，生成01log文件记录错误信息
    start_time = time.time()  # 子线程执行计时起始点，用于计算执行耗时
    t11 = time.time()  # 子线程执行计时起始点，用于计算执行耗时
    ssh = None         # 初始化SSH连接对象

    # 输出调试信息：idna模块路径和sys.path（当前已注释）
    # print(f"idna路径: {idna.__file__}")
    # print(f"sys.path: {sys.path}")

    try:  # 尝试登录设备
        # 记录连接尝试日志，包含超时时间信息
        log_message(f'设备 {login_info["host"]} 开始连接（超时时间 {login_info["conn_timeout"]} 秒）')
        ssh = ConnectHandler(
            session_log=os.path.join(LOG_DATE_DIR, f"{login_info['host']}.log"),  # 自动记录完整交互日志
            **login_info
        )
        # 使用设备登录信息，SSH登录设备，同时记录LOG日志
        # 仅当 secret 字段存在且非空时才执行 enable
        if login_info.get("secret"):
            ssh.enable()

    except Exception as ssh_error:  # 登录设备出现异常
        exception_name = type(ssh_error).__name__  # 获取异常类型名称

        # 根据不同异常类型生成针对性日志
        if exception_name == 'AttributeError':
            log_message(f'设备 {login_info["host"]} 缺少设备管理地址！')
        elif exception_name == 'NetmikoTimeoutException':
            log_message(f'设备 {login_info["host"]} 管理地址或端口不可达！')
        elif exception_name == 'NetmikoAuthenticationException':
            log_message(f'设备 {login_info["host"]} 用户名或密码认证失败！')
        elif exception_name == 'ValueError':
            if login_info.get("secret"):  # secret存在，说明设备期望进入enable
                log_message(f'设备 {login_info["host"]} Enable密码认证失败！')
            else:
                log_message(f'设备 {login_info.get("host", "未知设备")} 不需要Enable密码，已跳过。')
        elif exception_name == 'TimeoutError':
            log_message(f'设备 {login_info["host"]} Telnet连接超时！')
        elif exception_name == 'ReadTimeout':
            if login_info.get("secret"):
                log_message(f'设备 {login_info["host"]} Enable密码认证失败！（ReadTimeout）')
            else:
                log_message(f'设备 {login_info["host"]} 不需要Enable密码（ReadTimeout），已跳过。')
        elif exception_name == 'ConnectionRefusedError':
            log_message(f'设备 {login_info["host"]} 远程登录协议错误！')
        elif exception_name == 'TypeError':
            log_message(f'设备 {login_info["host"]} 登录信息格式异常，可能缺字段！')
        else:
            log_message(f'设备 {login_info["host"]} 未知错误！{type(ssh_error).__name__}: {str(ssh_error)}')
            return  # ✅ 必须添加此行，避免继续执行else块

    else:  # 如果登录正常，开始执行巡检命令
        # 安全冗余检查：防止异常情况下ssh对象未正确创建
        if ssh is None:
            log_message(f"[异常保护] 设备 {login_info['host']} SSH 连接对象未建立，跳过巡检。")
            return

        # 获取设备真实主机名（通过SSH会话提示符解析）
        real_hostname = ssh.find_prompt().strip()

        # 加锁同步控制台输出，避免多线程打印混乱
        with LOCK:
            print(f'设备 {login_info["host"]} 正在巡检...')

        # 定义无回显命令集合（执行后通常无输出，需特殊处理）
        NO_OUTPUT_CMDS = {
            "sys", "enable", "user-inter con 0", "quit",
            "undo screen-length", "screen-length disable",
            "screen-length enable", "screen-length 0",
            "screen-length 0 temporary"
        }

        # 遍历当前设备类型对应的所有巡检命令
        for cmd in cmds_dict[login_info['device_type']]:
            elapsed = time.time() - t11  #计算当前命令执行耗时
            remaining = INSPECTION_TASK_TIMEOUT - elapsed  #计算剩余时间
            # ---------- 新增超时检查 -----------
            if remaining <= 0:
                log_message(f'设备 {login_info["host"]} 巡检任务超时，已主动中止')
                return
            # 计算当前命令的超时时间（取剩余时间和单条命令最大超时的较小值）
            timeout_per_cmd = min(INSPECTION_CMD_TIMEOUT, remaining)
            # ---------- 原有命令执行逻辑 ----------
            if isinstance(cmd, str):  # 仅处理字符串类型的命令（排除可能的复合指令）
                show = "命令执行前初始化失败"  # 初始化变量，确保所有路径都有定义
                try:
                    # 对无回显命令使用send_command_timing（兼容无输出场景）
                    if cmd.strip().lower() in NO_OUTPUT_CMDS:
                        # 添加超时参数，单位为秒（时间为超时时间）
                        show = ssh.send_command_timing(cmd, read_timeout=timeout_per_cmd)
                        # 处理回显中包含的错误信息
                        # 处理无输出情况
                        if show.strip() == "":
                            show = f"命令 {cmd} 执行完毕，无输出。"
                        elif show.strip() == cmd:
                            show = f"命令 {cmd} 已发送，但可能无回显或未生效。"
                    else:
                        #添加超时参数，单位为秒（时间为超时时间）
                        show = ssh.send_command(cmd, read_timeout=timeout_per_cmd)

                except exceptions.ReadTimeout as e:
                    # 处理命令执行超时异常
                    log_message(f'设备 {login_info["host"]} 命令 {cmd} 执行超时: {str(e)}')
                    show = f'命令 {cmd} 执行超时: {str(e)}'
                except Exception as e:
                    # 捕获其他未预料到的异常
                    log_message(f'设备 {login_info["host"]} 命令 {cmd} 执行异常: {type(e).__name__}: {str(e)}')
                    show = f'命令 {cmd} 执行异常: {str(e)}'
                finally:
                    # 检测不识别的命令（通过^符号和错误关键词判断）
                    if '^' in show and 'Unrecognized command' in show:
                        log_message(f'设备 {login_info["host"]} 命令 {cmd} 不兼容或错误：{show.strip().splitlines()[-1]}')

                    # 根据用户设置决定是否在控制台显示回显
                    if show_output == 'y':
                        with LOCK:  # 加锁同步控制台输出
                            print(f'{real_hostname} {cmd} 回显如下：\n{show}\n')

    finally:  # 无论登录成功与否，最终执行资源清理
        try:
            if ssh is not None:  # 确保ssh对象已正确创建
                ssh.disconnect()  # 关闭SSH连接
        except Exception as e:
            log_message(f"设备 {login_info['host']} 断开连接失败: {str(e)}")
        finally:
            # 计算并记录任务总耗时
            t12 = time.time()
            log_message(f"设备 {login_info['host']} 巡检完成，耗时 {round(t12 - t11, 2)} 秒")
            log_message(f"设备 {login_info['host']} SSH连接已关闭，任务资源已释放")


from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeout

# 自定义守护线程池执行器
# 继承自ThreadPoolExecutor，重写_worker方法确保所有工作线程为守护线程
# 解决主线程退出后子线程仍可能残留的问题
class DaemonThreadPoolExecutor(ThreadPoolExecutor):
    """自定义守护线程池，确保主线程退出时所有子线程随之终止"""
    def _worker(self, *args, **kwargs):
        thread = threading.current_thread()
        thread.daemon = True  # 设置为守护线程
        super()._worker(*args, **kwargs)

if __name__ == '__main__':
    #主线程计时器t1,计算巡检总耗时
    t1 = time.time()
    # 读取设备信息和命令配置
    devices_info, cmds_info = read_info()
    # 获取用户输入，是否显示实时命令输出（默认不显示）
    show_output = input("是否显示实时命令输出？(y/n, 默认n): ").strip().lower() or 'n'

    log_message('>>> 本次为首次巡检 <<<')
    print(f'\n巡检开始...')
    print(f'\n' + '>' * 40 + '\n')

    # 日志文件路径处理 - 修正为logs根目录（而非日期子目录）
    log_file_path = os.path.join(LOG_DIR, '01log.log')  # 修改LOG_DATE_DIR为LOG_DIR
    try:
        # 先检查文件是否存在，避免误报
        if os.path.exists(log_file_path):
            log_message(f'文件存在,删除陈旧01log。')
            os.remove(log_file_path)
        else:
            # 添加调试信息：打印实际查找的路径
            log_message(f'01log.log文件不存在,无需删除。[实际查找路径: {log_file_path}]')
    except OSError as e:
        # 捕获所有系统相关异常（权限/占用/路径错误等）
        log_message(f'删除01log文件失败: {str(e)}')
        # 备选方案：尝试清空文件内容而非删除
        try:
            with open(log_file_path, 'w') as f:
                pass  # 以写入模式打开文件会清空内容
            log_message(f'已清空01log文件内容(删除失败后的备选处理)。')
        except Exception as clear_e:
            log_message(f'清空01log文件失败: {str(clear_e)}')

    # 线程池配置 - 动态调整大小
    # 1. 获取CPU核心数（处理可能为None的情况，默认使用4核心）
    # 2. 计算最大工作线程数：设备数量、CPU核心数*5、200的最小值
    #    确保线程池不会过度消耗系统资源
    cpu_count = os.cpu_count() or 4  # 处理 None 情况，默认使用 4 核心
    max_workers = min(len(devices_info), cpu_count * 5, 200)

    # 使用自定义守护线程池执行巡检任务
    # thread_name_prefix用于调试时识别线程来源
    with DaemonThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='DeviceInspect') as executor:
        futures = []
        # 遍历所有设备信息，提交巡检任务
        for device_info in devices_info:
            # 验证设备信息必填字段
            required_fields = ['device_type', 'host', 'ip', 'username']
            if not all(device_info.get(field) and str(device_info.get(field)).strip() != '' for field in required_fields):
                log_message(f"[跳过] 设备信息字段不完整，已跳过：{device_info}")
                continue

            # 复制设备信息并添加连接超时配置
            updated_device_info = device_info.copy()
            updated_device_info["conn_timeout"] = 15  # 设置连接超时为15秒

            # 提交巡检任务到线程池
            # inspection: 实际执行巡检的函数
            # updated_device_info: 设备连接信息
            # cmds_info: 命令配置信息
            # show_output: 是否显示实时输出标志
            future = executor.submit(
                inspection,
                updated_device_info,
                cmds_info,
                show_output
            )
            # 存储future对象和对应的主机名，用于后续结果处理
            futures.append((future, device_info['host']))
            log_message(f"[线程池] 已提交任务: {device_info['host']}")

        # 处理所有任务结果
        for future, host in futures:
            try:
                # 获取任务结果，设置超时时间为INSPECTION_TASK_TIMEOUT秒+几秒冗余（如+5），避免边界误判
                future.result(timeout=INSPECTION_TASK_TIMEOUT+5)
            except FutureTimeout:
                # 理论上inspection内已经做了超时自我终止
                log_message(f"设备 {host} 巡检任务超时（>{INSPECTION_TASK_TIMEOUT}秒），请检查inspection函数内部超时控制是否生效")
            except Exception as e:
                log_message(f"设备 {host} 巡检任务异常: {str(e)}")

    # 统计错误设备数量
    try:
        error_devices = set()
        # 读取日志文件，提取错误设备信息
        with open(os.path.join(LOG_DIR, '01log.log'), 'r', encoding='utf-8') as log_file:
            for line in log_file:
                if line.startswith('设备 '):
                    parts = line.split()
                    if len(parts) >= 2:
                        error_devices.add(parts[1])
            file_lines = len(error_devices)
    except FileNotFoundError:
        file_lines = 0

    #主线程计时器t2,计算巡检总耗时
    t2 = time.time()
    log_message(f'\n' + '<' * 40 + '\n')
    log_message(f'巡检完成，共巡检 {len(futures)} 台设备，{file_lines} 台异常，共用时 {round(t2 - t1, 1)} 秒。\n')
    log_message(f"线程池已关闭，所有任务已完成")
    input('输入Enter退出！')