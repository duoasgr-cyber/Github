import sys
import os

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

from ui.main_window import MainWindow
from core.config_manager import ConfigManager
from core.logger import setup_logging, get_logger


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    config_manager = ConfigManager(base_dir)
    log_file = config_manager.get_config("logging.log_file") or "app.log"
    log_level = config_manager.get_config("logging.log_level", "INFO")
    setup_logging(log_file=log_file, level=log_level)

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)

    qss_path = os.path.join(base_dir, "ui", "resources", "style.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    icon_path = os.path.join(base_dir, "ui", "resources", "icons", "app.svg")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Show setup wizard on first run
    try:
        from ui.dialogs.setup_wizard import SetupWizardDialog
        if SetupWizardDialog.should_show_on_startup(base_dir):
            wizard = SetupWizardDialog(base_dir)
            wizard.exec_()
    except Exception as e:
        import logging
        logging.info("Setup wizard 跳过或失败: %s", e)  # Wizard is non-blocking

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger = get_logger("unhandled")
    logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))

    # Report to telemetry
    try:
        from core.telemetry import Telemetry
        import traceback
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        Telemetry().record_crash(exc_type.__name__, str(exc_value), tb_text)
    except Exception as e:
        logger.debug("崩溃遥测发送失败: %s", e)
    app = QApplication.instance()
    if app:
        QMessageBox.critical(
            None,
            "Application Error",
            "An unhandled exception occurred:\n{}: {}".format(exc_type.__name__, exc_value),
        )


if __name__ == "__main__":
    sys.excepthook = handle_exception

    try:
        main()
    except KeyboardInterrupt:
        app = QApplication.instance()
        if app:
            app.quit()
        sys.exit(0)
    except Exception as e:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        logger = get_logger("startup")
        logger.critical("Startup failed", exc_info=True)
        QMessageBox.critical(
            None,
            "Startup Failed",
            "Application startup failed:\n{}: {}".format(type(e).__name__, e),
        )
        sys.exit(1)