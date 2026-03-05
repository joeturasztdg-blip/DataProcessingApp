from dataclasses import dataclass

from utils.logging import Logger

from processing.cleansing import DataCleaner
from processing.headers import HeaderDetector
from processing.loading import FileLoader
from processing.transforms import DomainTransforms
from processing.packaging import ZipEncryptor
from processing.repos.seeds_repo import SeedsRepository
from processing.repos.postcodes_repo import PostcodesRepository
from gui.password_broker import PasswordBroker

@dataclass
class Services:
    logger: Logger
    password_broker: PasswordBroker
    cleaner: DataCleaner
    headers: HeaderDetector
    transforms: DomainTransforms
    packager: ZipEncryptor
    seeds_repo: SeedsRepository
    postcodes_repo: PostcodesRepository
    loader: FileLoader

def build_services(window) -> Services:
    logger = Logger(lambda msg, _c=None: window.log_signal.emit(msg))

    password_broker = PasswordBroker(window)

    cleaner = DataCleaner(logger)
    headers = HeaderDetector(logger)
    transforms = DomainTransforms()
    packager = ZipEncryptor()
    seeds_repo = SeedsRepository()
    postcodes_repo = PostcodesRepository()

    loader = FileLoader(
        header_detector=headers,
        cleaner=cleaner,
        logger=logger,
        password_callback=password_broker.get_password)
    
    return Services(
        logger=logger,
        password_broker=password_broker,
        cleaner=cleaner,
        headers=headers,
        transforms=transforms,
        packager=packager,
        seeds_repo=seeds_repo,
        postcodes_repo=postcodes_repo,
        loader=loader)