# Copyright (c) 2022 Chris Duf <chris@openmarl.org>
#
# SPDX-License-Identifier: Apache-2.0

"""Devicetree shell session."""

import os
import readline
import signal
import sys

from devicetree.edtlib import Node, Binding

from rich.text import Text

from dtsh.dtsh import Dtsh, DtshCommand, DtshCommandOption, DtshSession, DtshError
from dtsh.dtsh import DtshCommandNotFoundError, DtshCommandUsageError, DtshCommandFailedError
from dtsh.shell import DevicetreeShell
from dtsh.term import DevicetreeTerm
from dtsh.autocomp import DevicetreeAutocomp
from dtsh.rich import DtshTheme


class DevicetreeShellSession(DtshSession):
    """Shell session with GNU readline history support.
    """

    _dtsh: Dtsh
    _term: DevicetreeTerm
    _last_err: DtshError | None

    def __init__(self, shell: Dtsh, term: DevicetreeTerm) -> None:
        """Creates a session.

        Arguments:
        shell - the session's shell instance
        term - the session's rich VT
        """
        self._dtsh = shell
        self._term = term
        self._last_err = None

        self.readline_read_history()

    @property
    def term(self) -> DevicetreeTerm:
        """Session's VT."""
        return self._term

    @property
    def last_err(self) -> DtshError | None:
        return self._last_err

    def run(self):
        """Overrides DtshSession.run().
        """
        self._term.clear()
        self.banner()

        while True:
            try:
                self._term.write(DtshTheme.mk_node_path(self._dtsh.pwd))
                prompt = DtshTheme.mk_ansi_prompt(self._last_err is not None)
                cmdline = self._term.readline(prompt)
                if cmdline:
                    if cmdline in ['q', 'quit', 'exit']:
                        self.close()
                    self._dtsh.exec_command_string(cmdline, self._term)
                    self._last_err = None
                else:
                    # Also reset error state on empty command line.
                    self._last_err = None

            except DtshCommandNotFoundError as e:
                self._last_err = e
                self._term.write(f'dtsh: Command not found: {e.name}')
            except DtshCommandUsageError as e:
                self._last_err = e
                self._term.write(f'{e.command.name}: {e.msg}')
            except DtshCommandFailedError as e:
                self._last_err = e
                self._term.write(f'{e.command.name}: {e.msg}')
            except EOFError:
                self._term.abort()
                self.close()
            if DtshTheme.OPTION_SPARSE_PROMPT:
                self._term.write()

    def close(self) -> None:
        """Overrides DtshSession.close().
        """
        self._term.write('bye.', style=DtshTheme.STYLE_ITALIC)
        self.readline_write_history()
        sys.exit(0)

    def banner(self):
        """
        """
        view = Text().append_tokens(
            [
                ('dtsh', DtshTheme.STYLE_BOLD),
                (f" ({Dtsh.API_VERSION}): ", DtshTheme.STYLE_DEFAULT),
                ('Shell-like interface to a devicetree', DtshTheme.STYLE_ITALIC)
            ]
        )
        self._term.write(view)
        self._term.write()

    def configuration_path(self) -> str:
        xdg_cfg_dir = os.environ.get('XDG_CONFIG_HOME')
        if not xdg_cfg_dir:
            home = os.path.expanduser('~')
            xdg_cfg_dir = os.path.join(home, '.config')
        return os.path.join(xdg_cfg_dir, 'dtsh')

    def readline_hist_path(self) -> str:
        return os.path.join(self.configuration_path(), 'dtsh_history')

    def readline_read_history(self):
        hist_path = self.readline_hist_path()
        if os.path.isfile(hist_path):
            readline.read_history_file(hist_path)

    def readline_write_history(self):
        cfg_path = self.configuration_path()
        if not os.path.isdir(cfg_path):
            os.mkdir(cfg_path)
        readline.write_history_file(self.readline_hist_path())

    @staticmethod
    def open(dt_source_path: str | None = None,
             dt_bindings_path: list[str] | None = None) -> DtshSession:
        """
        """
        global _session
        global _autocomp

        if _session is not None:
            raise DtshError('Session already opened')

        shell = DevicetreeShell.create(dt_source_path, dt_bindings_path)
        term = DevicetreeTerm(
            readline_completions_hook,
            readline_display_hook
        )
        _session = DevicetreeShellSession(shell, term)
        _autocomp = DevicetreeAutocomp(shell)

        # We disable SIGINT (CTRL-C event).
        signal.signal(signal.SIGINT, dtsh_session_sig_handler)

        return _session


# Shell session singleton state.
_session: DevicetreeShellSession | None = None
_autocomp: DevicetreeAutocomp | None = None


def readline_completions_hook(text: str, state: int) -> str | None:
    if _autocomp is None:
        return None

    cmdline = readline.get_line_buffer()
    completions = _autocomp.autocomplete(cmdline, text, 0)

    if state < len(completions):
        return completions[state]
    return None


def readline_display_hook(substitution, matches, longest_match_length) -> None:
    if (_session is None) or (_autocomp is None):
        return

    cmdline = readline.get_line_buffer()

    # Go bellow input line
    _session.term.write()

    if _autocomp.model:
        m0 = _autocomp.model[0]
        if isinstance(m0, DtshCommand):
            model = list[DtshCommand](_autocomp.model)
            view = DtshTheme.mk_command_hints_display(model)
        elif isinstance(m0, DtshCommandOption):
            model = list[DtshCommandOption](_autocomp.model)
            view = DtshTheme.mk_option_hints_display(model)
        elif isinstance(m0, Binding):
            model = list[Binding](_autocomp.model)
            view = DtshTheme.mk_binding_hints_display(model)
        elif isinstance(m0, Node):
            model = list[Node](_autocomp.model)
            view = DtshTheme.mk_node_hints_display(model)
        else:
            view = DtshTheme.mk_grid(1)
            for m in _autocomp.model:
                view.add_row(Text(str(m), DtshTheme.STYLE_DEFAULT))
        _session.term.write(view)

    _session.term.write(DtshTheme.mk_ansi_prompt(), end='')
    _session.term.write(cmdline, end='')
    sys.stdout.flush()


def dtsh_session_sig_handler(signum, frame):
    # FIXME: closing() the session when the pager is active
    # breaks the TTY.
    # As a work-around, we ignore SIGINT.
    if signum == signal.SIGINT:
        return
