from modules.app_control import open_app, open_website
from modules.file_manager import search_files, format_results
from modules.system_info import get_system_info
from modules.process_manager import (
    get_process_list,
    format_process_list,
    find_process,
    get_process_info,
    get_top_processes
)
from modules.power_manager import (
    lock_pc,
    sleep_pc,
    shutdown_pc,
    restart_pc
)
from modules.task_manager import recognize_command


def execute_command(text):
    command = recognize_command(text)

    command_type = command["type"]
    argument = command["argument"]

    if command_type == "empty":
        return {"success": False, "response": "Команда пустая"}

    if command_type == "chat":
        return {
            "success": True,
            "action": "chat",
            "response": None
        }

    try:
        if command_type == "open_app":
            result = open_app(argument)

        elif command_type == "open_website":
            result = open_website(argument)

        elif command_type == "search_files":
            if not argument:
                return {
                    "success": False,
                    "response": "Укажи название файла"
                }

            results = search_files(argument)
            result = format_results(results)

        elif command_type == "system_info":
            result = get_system_info()

        elif command_type == "processes":
            processes = get_process_list()
            result = format_process_list(processes)

        elif command_type == "lock_pc":
            result = lock_pc()

        elif command_type == "sleep_pc":
            result = sleep_pc()

        elif command_type == "shutdown_pc":
            return {
                "success": True,
                "action": "confirmation_required",
                "command": "shutdown_pc",
                "response": "Ты действительно хочешь выключить компьютер?"
            }

        elif command_type == "restart_pc":
            return {
                "success": True,
                "action": "confirmation_required",
                "command": "restart_pc",
                "response": "Ты действительно хочешь перезагрузить компьютер?"
            }

        elif command_type == "stop":
            return {
                "success": True,
                "action": "stop",
                "response": "Хорошо, отменяю."
            }

        else:
            return {
                "success": False,
                "response": "Неизвестная команда"
            }

        return {
            "success": True,
            "action": "completed",
            "response": str(result)
        }

    except Exception as error:
        return {
            "success": False,
            "action": "error",
            "response": f"Ошибка выполнения команды: {error}"
        }


def confirm_command(command_type, confirmed):
    if not confirmed:
        return {
            "success": True,
            "response": "Действие отменено."
        }

    if command_type == "shutdown_pc":
        result = shutdown_pc()

    elif command_type == "restart_pc":
        result = restart_pc()

    else:
        return {
            "success": False,
            "response": "Неизвестное действие."
        }

    return {
        "success": True,
        "action": "completed",
        "response": str(result)
    }
