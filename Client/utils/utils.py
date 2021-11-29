import logging


def logger_config(log_name):
    logger = logging.getLogger(log_name)
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler('Logs/' + log_name +'.txt')
    formatter = logging.Formatter('%(asctime)s : %(levelname)s : %(name)s : %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger
