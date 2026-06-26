# -*- coding: utf-8 -*-
"""MySQL 연결 및 SQLAlchemy 엔진 관리 모듈"""

import os

import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.config.envLoader import getDbConfig, getProjectRoot, loadProjectEnv


def buildMysqlUrl(dbConfig, includeDatabase=True):
    """SQLAlchemy MySQL 연결 URL을 생성한다."""
    host = dbConfig.get("host", "127.0.0.1")
    port = dbConfig.get("port", 3306)
    user = dbConfig.get("user", "")
    password = dbConfig.get("password", "")
    database = dbConfig.get("database", "")

    if includeDatabase is True and database != "":
        return (
            "mysql+pymysql://"
            + user
            + ":"
            + password
            + "@"
            + host
            + ":"
            + str(port)
            + "/"
            + database
            + "?charset=utf8mb4"
        )

    return (
        "mysql+pymysql://"
        + user
        + ":"
        + password
        + "@"
        + host
        + ":"
        + str(port)
        + "/?charset=utf8mb4"
    )


def getDbEngine(includeDatabase=True):
    """SQLAlchemy Engine 인스턴스를 반환한다."""
    loadProjectEnv()
    dbConfig = getDbConfig()
    mysqlUrl = buildMysqlUrl(dbConfig, includeDatabase=includeDatabase)
    engine = create_engine(
        mysqlUrl,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    return engine


def getRawConnection(includeDatabase=True):
    """pymysql 직접 연결 객체를 반환한다."""
    loadProjectEnv()
    dbConfig = getDbConfig()
    connectArgs = {
        "host": dbConfig.get("host", "127.0.0.1"),
        "port": int(dbConfig.get("port", 3306)),
        "user": dbConfig.get("user", ""),
        "password": dbConfig.get("password", ""),
        "charset": "utf8mb4",
        "connect_timeout": 10,
    }
    if includeDatabase is True:
        connectArgs["database"] = dbConfig.get("database", "")

    connection = pymysql.connect(**connectArgs)
    return connection


def testDbConnection():
    """DB 연결 가능 여부를 검증한다."""
    try:
        connection = getRawConnection(includeDatabase=False)
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        connection.close()
        return {"success": True, "message": "MySQL 연결 성공"}
    except Exception as connectionError:
        return {
            "success": False,
            "message": "MySQL 연결 실패: " + str(connectionError),
        }


def ensureDatabaseExists():
    """설정된 데이터베이스가 없으면 생성한다."""
    loadProjectEnv()
    dbConfig = getDbConfig()
    databaseName = dbConfig.get("database", "")
    if databaseName == "":
        return {"success": False, "message": "DB_NAME이 설정되지 않았습니다."}

    try:
        connection = getRawConnection(includeDatabase=False)
        with connection.cursor() as cursor:
            createSql = (
                "CREATE DATABASE IF NOT EXISTS `"
                + databaseName
                + "` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.execute(createSql)
        connection.commit()
        connection.close()
        return {
            "success": True,
            "message": "데이터베이스 확인/생성 완료: " + databaseName,
            "database": databaseName,
        }
    except Exception as databaseError:
        return {
            "success": False,
            "message": "데이터베이스 생성 실패: " + str(databaseError),
        }


def getSchemaSqlPath():
    """DDL 스키마 SQL 파일 경로를 반환한다."""
    projectRoot = getProjectRoot()
    return os.path.join(projectRoot, "sql", "schema.sql")


def readSchemaSql():
    """DDL 스키마 SQL 파일 내용을 읽는다."""
    schemaPath = getSchemaSqlPath()
    if os.path.exists(schemaPath) is False:
        return {
            "success": False,
            "message": "스키마 파일이 없습니다: " + schemaPath,
        }

    with open(schemaPath, "r", encoding="utf-8") as schemaFile:
        schemaSql = schemaFile.read()

    return {
        "success": True,
        "message": "스키마 SQL 로드 완료",
        "schemaPath": schemaPath,
        "schemaSql": schemaSql,
    }


def stripSqlComments(schemaSql):
    """SQL 파일 내 단일행 주석(--)을 제거한다."""
    lines = schemaSql.split("\n")
    cleanedLines = []
    for i in range(0, len(lines)):
        lineText = lines[i].strip()
        if lineText.startswith("--"):
            continue
        cleanedLines.append(lines[i])
    return "\n".join(cleanedLines)


def splitSqlStatements(schemaSql):
    """세미콜론 기준으로 SQL 문을 분리한다."""
    cleanedSql = stripSqlComments(schemaSql)
    rawParts = cleanedSql.split(";")
    statements = []
    for i in range(0, len(rawParts)):
        statement = rawParts[i].strip()
        if statement == "":
            continue
        statements.append(statement)
    return statements


def executeSchemaSql(engine):
    """DDL 스키마 SQL을 실행한다."""
    schemaResult = readSchemaSql()
    if schemaResult.get("success") is not True:
        return schemaResult

    schemaSql = schemaResult.get("schemaSql", "")
    statements = splitSqlStatements(schemaSql)
    executedCount = 0

    try:
        with engine.begin() as connection:
            for i in range(0, len(statements)):
                statement = statements[i]
                connection.execute(text(statement))
                executedCount = executedCount + 1

        return {
            "success": True,
            "message": "스키마 DDL 실행 완료",
            "executedCount": executedCount,
            "schemaPath": schemaResult.get("schemaPath", ""),
        }
    except Exception as schemaError:
        return {
            "success": False,
            "message": "스키마 DDL 실행 실패: " + str(schemaError),
        }


def getTableList(engine):
    """현재 데이터베이스의 테이블 목록을 반환한다."""
    tableNames = []
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SHOW TABLES"))
            rows = result.fetchall()
            for i in range(0, len(rows)):
                tableNames.append(rows[i][0])
        return {"success": True, "message": "테이블 목록 조회 완료", "tables": tableNames}
    except Exception as listError:
        return {
            "success": False,
            "message": "테이블 목록 조회 실패: " + str(listError),
        }