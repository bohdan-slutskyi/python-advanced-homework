"""Настройка совместимости PyMySQL с Django MySQL backend."""

import pymysql


# Django ожидает интерфейс MySQLdb при выборе MySQL backend.
pymysql.install_as_MySQLdb()
