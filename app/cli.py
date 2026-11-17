from app.api import ServerCommunicationError, activate
from app.config import ConfigError, Message, read_config
from app.device import DeviceError, collect_device
from app.input_license import input_license
from app.licensing import PATTERN, valid_license


def run() -> int:
    status = 1
    try:
        config = read_config()
        key = input_license()
        if PATTERN.fullmatch(key) is None:
            print(Message.error.invalid_license_format)
        elif not valid_license(key):
            print(Message.error.invalid_license_checksum)
        else:
            device = collect_device()
            result = activate(config, key, device)
            print(result.message)
            status = 0 if result.success else 1
    except (ConfigError, DeviceError, ServerCommunicationError) as exc:
        print(str(exc))
    except (EOFError, KeyboardInterrupt):
        print(Message.error.input_interrupted)
    finally:
        try:
            input(Message.info.press_enter_to_exit)
        except (EOFError, KeyboardInterrupt):
            pass
    return status
