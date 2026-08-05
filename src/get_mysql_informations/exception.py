from __future__ import annotations

from typing import NoReturn

import typer

from .ui.console import console


class CliExceptionHandler:
    """
    针对cli 应用的异常处理
    """

    def handle(
            self,
            exc: Exception,
    ) -> NoReturn:
        self._handle_unexpected_error(exc)




    def _handle_unexpected_error(
            self,
            exc: Exception,
    ) -> NoReturn:

        console.error("An unexpected error occurred.")

        console.print_exception()

        raise typer.Exit()

