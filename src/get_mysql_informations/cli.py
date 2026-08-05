from __future__ import annotations

import csv
import time
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import mysql.connector
import typer
from mysql.connector.connection import MySQLConnection

from .decorators import command_handler
from .ui.console import console, create_progress

# =========================
# 通用函数
# =========================

def now_for_file() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005


def now_human() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # noqa: DTZ005


def connect_mysql(mysql_config: dict) -> MySQLConnection:
    return mysql.connector.connect(**mysql_config) # type: ignore



def ensure_output_dir(output: str) -> None:
    Path(output).mkdir(parents=True, exist_ok=True)




def export_rows_to_csv(
    filename: Path,
    columns: list[str],
    rows: list[Any],
) -> None:
    with filename.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)


def run_query_to_csv(
    conn: MySQLConnection,
    query_name: str,
    sql: str,
    filename: Path,
) -> None:
    """
    通用 SQL 采集函数。
    适用于 SELECT 或 SHOW 返回表格结果的语句。
    """
    try:
        cursor = conn.cursor()
        cursor.execute(sql)

        rows = cursor.fetchall()

        if cursor.description:
            columns = [col[0] for col in cursor.description]
        else:
            columns = []

        export_rows_to_csv(filename, columns, rows)

        print(f"[{now_human()}] Saved {query_name}: {filename}")

    except Exception as ex:
        print(f"[{now_human()}] ERROR collecting {query_name}: {ex}")
        raise


# =========================
# 采集项 1: SHOW FULL PROCESSLIST
# =========================

def collect_processlist(conn: MySQLConnection, timestamp: str, outputdir:str) -> None:
    filename = Path(outputdir) / f"processlist_{timestamp}.csv"

    sql = "SHOW FULL PROCESSLIST"

    run_query_to_csv(
        conn=conn,
        query_name="processlist",
        sql=sql,
        filename=filename,
    )


# =========================
# 采集项 2: SHOW ENGINE INNODB STATUS
# =========================

def collect_innodb_status(conn: MySQLConnection, timestamp: str, outputdir: str) -> None:
    filename = Path(outputdir) / f"innodb_status_{timestamp}.txt"

    try:
        cursor = conn.cursor()
        cursor.execute("SHOW ENGINE INNODB STATUS")
        row = cursor.fetchone()

        with filename.open("w", encoding="utf-8") as f:
            f.write(f"Collection Time: {now_human()}\n")
            f.write("=" * 100)
            f.write("\n\n")

            if row:
                # 通常返回列为:
                # Type, Name, Status
                # Status 一般是第 3 列，也就是 row[2]
                if len(row) >= 3:
                    f.write(str(row[2]))
                else:
                    f.write(str(row))
            else:
                f.write("No result returned by SHOW ENGINE INNODB STATUS.\n")

        print(f"[{now_human()}] Saved innodb_status: {filename}")

    except Exception as ex:
        print(f"[{now_human()}] ERROR collecting innodb_status: {ex}")
        raise

# =========================
# 采集项 3: SHOW GLOBAL STATUS
# =========================

def collect_global_status(conn: MySQLConnection, timestamp: str, outputdir: str) -> None:
    filename = Path(outputdir) / f"global_status_{timestamp}.csv"

    sql = "SHOW GLOBAL STATUS"

    run_query_to_csv(
        conn=conn,
        query_name="global_status",
        sql=sql,
        filename=filename,
    )


# =========================
# 采集项 4: SHOW GLOBAL VARIABLES
# =========================

def collect_global_variables(outputdir: str, conn: MySQLConnection) -> None:
    filename = Path(outputdir) / "global_variables.csv"

    sql = "SHOW GLOBAL VARIABLES"

    run_query_to_csv(
        conn=conn,
        query_name="global_variables",
        sql=sql,
        filename=filename,
    )


# =========================
# 采集项 5: SHOW ENGINE PERFORMANCE_SCHEMA STATUS
# =========================

def collect_performance_schema_status(conn: MySQLConnection, timestamp: str, outputdir: str) -> None:
    filename = Path(outputdir) / f"performance_schema_status_{timestamp}.csv"

    sql = "SHOW ENGINE PERFORMANCE_SCHEMA STATUS"

    run_query_to_csv(
        conn=conn,
        query_name="performance_schema_status",
        sql=sql,
        filename=filename,
    )


# =========================
# 采集项 6: information_schema.innodb_trx
# =========================

def collect_innodb_trx(conn: MySQLConnection, timestamp: str, outputdir: str) -> None:
    filename = Path(outputdir) / f"innodb_trx_{timestamp}.csv"

    sql = """
    SELECT *
    FROM information_schema.innodb_trx
    """

    run_query_to_csv(
        conn=conn,
        query_name="innodb_trx",
        sql=sql,
        filename=filename,
    )


# =========================
# 采集项 7: information_schema.innodb_lock_waits
# =========================

def collect_innodb_lock_waits(conn: MySQLConnection, timestamp: str, outputdir: str) -> None:
    filename = Path(outputdir) / f"innodb_lock_waits_{timestamp}.csv"

    sql = """
    SELECT *
    FROM performance_schema.data_lock_waits;
    """

    run_query_to_csv(
        conn=conn,
        query_name="innodb_lock_waits",
        sql=sql,
        filename=filename,
    )


# =========================
# 采集项 8: information_schema.innodb_locks
# =========================

def collect_innodb_locks(conn: MySQLConnection, timestamp: str, outputdir: str) -> None:
    filename = Path(outputdir) / f"innodb_locks_{timestamp}.csv"

    sql = """
    SELECT *
    FROM performance_schema.data_locks;
    """

    run_query_to_csv(
        conn=conn,
        query_name="innodb_locks",
        sql=sql,
        filename=filename,
    )


# =========================
# 额外检查: 用户库无主键表
# =========================

def collect_tables_without_primary_key(outputdir: str,  conn: MySQLConnection) -> None:
    filename = Path(outputdir) / "tables_without_primary_key.csv"

    sql = """
    SELECT
        t.table_schema,
        t.table_name,
        t.table_type,
        t.engine,
        t.table_rows,
        t.create_time,
        t.update_time
    FROM information_schema.tables AS t
    LEFT JOIN information_schema.table_constraints AS tc
        ON  t.table_schema = tc.table_schema
        AND t.table_name = tc.table_name
        AND tc.constraint_type = 'PRIMARY KEY'
    WHERE t.table_schema NOT IN
    (
        'mysql',
        'sys',
        'information_schema',
        'performance_schema'
    )
    AND t.table_type = 'BASE TABLE'
    AND tc.constraint_name IS NULL
    ORDER BY
        t.table_schema,
        t.table_name
    """

    run_query_to_csv(
        conn=conn,
        query_name="tables_without_primary_key",
        sql=sql,
        filename=filename,
    )


# =========================
# 每一轮动态采集
# =========================

def collect_one_round(conn: MySQLConnection, round_number: int, total_rounds: int, outputdir: str) -> None:
    timestamp = now_for_file()

    console.print("")
    console.print("=" * 100)
    console.print(f"[{now_human()}] Start collection round {round_number}/{total_rounds}")
    console.print("=" * 100)

    collect_processlist(conn, timestamp, outputdir)

    collect_innodb_status(conn, timestamp, outputdir)

    collect_global_status(conn, timestamp, outputdir)

    collect_performance_schema_status(conn, timestamp, outputdir)

    collect_innodb_trx(conn, timestamp, outputdir)

    collect_innodb_lock_waits(conn, timestamp, outputdir)

    collect_innodb_locks(conn, timestamp, outputdir)

    console.success(f"[{now_human()}] Completed collection round {round_number}/{total_rounds}")




app = typer.Typer()

@app.command()
@command_handler()
def get_mysql_running_information(
    host: Annotated[
        str,
        typer.Option(
            '--host',
            '-h',
            help="Azure Database for MySQL host name")
    ],

    port: Annotated[
        int,
        typer.Option(
            '--port',
            '-p',
            help="Azure Database for MySQL Port")
    ],

    username: Annotated[
        str,
        typer.Option(
            '--username',
            '-u',
            help="User Name")
    ],

    password: Annotated[
        str,
        typer.Option(
            '--password',
            '-p',
            help="Login Password")
    ],

    outputdir: Annotated[
        str,
        typer.Option(
            '--output',
            '-o',
            help="all result output directory")
    ] = "mysql_diagnostics_output",

    ssl_disabled: Annotated[
        bool,
        typer.Option(
            '--ssl-disabled',
            '-l',
            help='disabled the SSL Access'
        )
    ] = False,

    interval_seconds: Annotated[
        int,

        typer.Option(
            '--interval-seconds',
            '-i',
            help="Interval seconds"
        )
    ] = 300,

    total_rounds: Annotated[
        int,
        typer.Option(
            '--total-rounds',
            '-r',
            help="Total Rounds"
        )
    ] = 12,
) -> None:

    with console.status(
        "[cyan]Checking output directory, confirm it can be access......"
    ):
        time.sleep(2)
        ensure_output_dir(outputdir)
        console.success(f"[{now_human()}] Output directory: {Path(outputdir).resolve()}")


    with console.status(
        "[cyan]checking and try to connect to MySQL..."
    ):
        time.sleep(2)
        console.info(f"[{now_human()}] Connecting to MySQL server...")

        MYSQL_CONFIG = {
            "host": host,
            "port": port,
            "user": username,
            "password": password,

            # Azure Database for MySQL 一般建议启用 SSL
            # 如果客户环境明确不需要 SSL，可以改为 True
            "ssl_disabled": ssl_disabled,
        }

        conn : MySQLConnection = connect_mysql(MYSQL_CONFIG)
        console.success(f"[{now_human()}] Connected successfully.")

    

    # 静态或低频信息，建议只采集一次

    with console.status(
        "[cyan]Collecting global variables..."
    ):
        time.sleep(2)
        collect_global_variables(outputdir, conn)
        console.success("Collected global variables successed.")


    with console.status(
        "[cyan]Find all tables which no primary key..."
    ):
        time.sleep(2)
        collect_tables_without_primary_key(outputdir, conn)
        console.success("All tables which no primary key was found out.")


    # 每5分钟采集一次，总共采取total rounds 次.

    with create_progress(console._console) as progress:
        overall_task = progress.add_task(
            "[cyan]Collecting diagnostics",
            total=total_rounds,
        )

        current_task = progress.add_task(
            "[green]Preparing...",
            total=1,
        )

        # 动态信息，每 5 分钟采集一次
        for i in range(total_rounds):

            round_no = i + 1

            if not conn.is_connected():
                progress.update(
                    current_task,
                    description="[yellow]Reconnecting MySQL...",
                    total=1,
                    completed=0,
                )

                conn.reconnect(
                    attempts=3,
                    delay=5,
                )

            progress.update(
                current_task,
                description=f"[green]Round {round_no}/{total_rounds}: Collecting data",
                total=1,
                completed=0,
            )

            collect_one_round(
                conn,
                round_no,
                total_rounds,
                outputdir,
            )

            progress.advance(current_task)

            progress.advance(overall_task)

            if i < total_rounds - 1:

                progress.update(
                    current_task,
                    description=f"[yellow]Round {round_no}/{total_rounds}: Waiting {interval_seconds}s",
                    total=interval_seconds,
                    completed=0,
                )

                for _ in range(interval_seconds):
                    time.sleep(1)
                    progress.advance(current_task)








if __name__ == "__main__":
    app()
