from dataclasses import dataclass

from utils.logging_adapter import LoggerAdapter

from processing.cleansing import DataCleaner
from processing.headers import HeaderDetector
from processing.loading import FileLoader
from processing.transforms import DomainTransforms
from processing.packaging import ZipEncryptor

from gui.password_broker import PasswordBroker


@dataclass
class Services:
    logger: LoggerAdapter
    password_broker: PasswordBroker
    cleaner: DataCleaner
    headers: HeaderDetector
    transforms: DomainTransforms
    packager: ZipEncryptor
    loader: FileLoader


def build_services(window) -> Services:
    """
    Construct and wire together all shared application services
    for the MainWindow.

    `window` is passed so PasswordBroker can parent dialogs
    and logger can emit into the UI.
    """

    logger = LoggerAdapter(lambda msg, _c=None: window.log_signal.emit(msg))

    password_broker = PasswordBroker(window)

    cleaner = DataCleaner(logger)
    headers = HeaderDetector(logger)
    transforms = DomainTransforms()
    packager = ZipEncryptor()

    loader = FileLoader(
        header_detector=headers,
        cleaner=cleaner,
        logger=logger,
        password_callback=password_broker.get_password,
    )

    return Services(
        logger=logger,
        password_broker=password_broker,
        cleaner=cleaner,
        headers=headers,
        transforms=transforms,
        packager=packager,
        loader=loader,
    )
