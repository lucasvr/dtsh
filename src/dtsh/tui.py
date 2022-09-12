# Copyright (c) 2022 Chris Duf <chris@openmarl.org>
#
# SPDX-License-Identifier: Apache-2.0

"""Devicetree shell UI components."""


import os
from typing import ClassVar

from devicetree.edtlib import Node, Binding, Property, PropertySpec, Register

from rich import box
from rich.console import RenderableType
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from rich.tree import Tree

from dtsh.dtsh import Dtsh, DtshVt


class DtshTui:

    # DTSH theme.
    _theme: ClassVar[Theme|None] = None

    # Common UTF-8 symbols.
    #
    WCHAR_PROMPT = '\u276f'
    WCHAR_ELLIPSIS = '\u2026'
    WCHAR_COPYRIGHT = '\u00a9'
    WCHAR_HYPHEN = '\u2014'
    WCHAR_DASH = '\ufe4d'
    WCHAR_ARROW = '\u2192'

    # Base styles.
    #
    STYLE_DEFAULT = 'dtsh.default'
    STYLE_APOLOGY = 'dtsh.apology'
    STYLE_TRUE = 'dtsh.true'
    STYLE_FALSE = 'dtsh.false'

    # Devicetree styles.
    #
    STYLE_DT_BINDING = 'dtsh.binding'
    STYLE_DT_COMPATS = 'dtsh.compats'
    STYLE_DT_LABEL = 'dtsh.label'
    STYLE_DT_LABELS = 'dtsh.labels'
    STYLE_DT_ALIAS = 'dtsh.alias'
    STYLE_DT_DESC = 'dtsh.desc'
    STYLE_DT_OKAY = 'dtsh.okay'
    STYLE_DT_NOT_OKAY = 'dtsh.not_okay'

    @staticmethod
    def theme() -> Theme:
        if DtshTui._theme is None:
            DtshTui._theme = DtshTui._load_theme()
        return DtshTui._theme

    @staticmethod
    def style(name: str) -> Style:
        style = DtshTui.theme().styles.get(name)
        if not style:
            style = Style()
        return style


    ############################################################################
    # Utils.
    ############################################################################

    @staticmethod
    def get_node_nick(node: Node) -> str:
        """Returns the node's name with the unit address part striped.
        """
        if node.unit_addr is not None:
            return node.name[0:node.name.rfind('@')]
        return node.name


    ############################################################################
    # Text
    ############################################################################

    @staticmethod
    def mk_txt(txt: str) -> Text:
        return Text(txt, DtshTui.style(DtshTui.STYLE_DEFAULT))

    @staticmethod
    def mk_txt_bool(is_true: bool,
                    true_str: str = 'Yes',
                    false_str: str = 'No',) -> Text:
        if is_true:
            val_str = true_str
            style = DtshTui.style(DtshTui.STYLE_TRUE)
        else:
            val_str = false_str
            style = DtshTui.style(DtshTui.STYLE_FALSE)
        return Text(val_str, style)

    @staticmethod
    def mk_txt_desc(desc: str | None) -> Text:
        if not desc:
            return Text("No description available.",
                        DtshTui.style(DtshTui.STYLE_APOLOGY))
        return Text(desc.strip(), DtshTui.style(DtshTui.STYLE_DT_DESC))

    @staticmethod
    def mk_txt_desc_short(desc: str | None) -> Text:
        if not desc:
            return Text()
        desc_lines = desc.strip().split('\n')
        desc_short = desc_lines[0]
        if len(desc_lines) > 1:
            if desc_short.endswith('.'):
                desc_short = desc_short[:-1]
            desc_short += DtshTui.WCHAR_ELLIPSIS
        return Text(desc_short, DtshTui.style(DtshTui.STYLE_DT_BINDING))

    @staticmethod
    def txt_update_link_file(txt: Text, path: str) -> None:
        txt.stylize(Style(link=f'file:{path}'))

    @staticmethod
    def txt_dim(txt: Text) -> None:
        if isinstance(txt.style, Style):
            style = txt.style.without_color
        else:
            style = Style.parse(txt.style).without_color
        # Note: Style.combine([DtshTui.style('dim')]) would also work
        style += DtshTui.style('dim')
        txt.style = style

    @staticmethod
    def mk_txt_node_status(node: Node) -> Text:
        if node.status == 'okay':
            style = DtshTui.style(DtshTui.STYLE_DT_OKAY)
        else:
            style = DtshTui.style(DtshTui.STYLE_DT_NOT_OKAY)
        return Text(node.status, style)

    @staticmethod
    def mk_txt_node_nick(node: Node, with_status: bool = False) -> Text:
        txt = Text(DtshTui.get_node_nick(node))
        if with_status and (node.status != 'okay'):
            DtshTui.txt_dim(txt)
        return txt

    @staticmethod
    def mk_txt_node_addr(node: Node, with_status: bool = False) -> Text:
        if node.unit_addr is None:
            return Text()
        txt = Text(hex(node.unit_addr))
        if with_status and (node.status != 'okay'):
            DtshTui.txt_dim(txt)
        return txt

    @staticmethod
    def mk_txt_node_binding(node: Node,
                            with_link: bool = True,
                            with_status: bool = False) -> Text:
        if not node.matching_compat:
            return Text()
        txt = Text(node.matching_compat, DtshTui.style(DtshTui.STYLE_DT_BINDING))
        if node.binding_path and with_link:
            DtshTui.txt_update_link_file(txt, node.binding_path)
        if with_status and (node.status != 'okay'):
            DtshTui.txt_dim(txt)
        return txt

    @staticmethod
    def mk_txt_node_compats(node: Node,
                            shell: Dtsh,
                            with_link: bool = True,
                            with_status: bool = False) -> Text:
        if not node.compats:
            return Text()
        txt_bindings = list[Text]()
        for compat in node.compats:
            txt = Text(compat, DtshTui.style(DtshTui.STYLE_DT_COMPATS))
            if compat == node.matching_compat:
                txt.stylize(DtshTui.style('bold'))
                binding = shell.dt_binding(compat)
                if binding and binding.path:
                    if with_link:
                        DtshTui.txt_update_link_file(txt, binding.path)
            if with_status and (node.status != 'okay'):
                DtshTui.txt_dim(txt)
            txt_bindings.append(txt)
        return Text(' ').join(txt_bindings)

    @staticmethod
    def mk_txt_node_label(node: Node, with_status: bool = False) -> Text:
        if not node.label:
            return Text()
        txt = Text(node.label, DtshTui.style(DtshTui.STYLE_DT_LABEL))
        if with_status and (node.status != 'okay'):
            DtshTui.txt_dim(txt)
        return txt

    @staticmethod
    def mk_txt_node_labels(node: Node, with_status: bool = False) -> Text:
        if not node.labels:
            return Text()
        txt_labels = list[Text]()
        for label in node.labels:
            txt = Text(label, DtshTui.style(DtshTui.STYLE_DT_LABELS))
            if with_status and (node.status != 'okay'):
                DtshTui.txt_dim(txt)
            txt_labels.append(txt)
        txt = Text(', ', DtshTui.style(DtshTui.STYLE_DEFAULT)).join(txt_labels)
        return txt

    @staticmethod
    def mk_txt_node_aliases(node: Node, with_status: bool = False) -> Text:
        if not node.aliases:
            return Text()
        txt_aliases = list[Text]()
        for alias in node.aliases:
            txt_aliases.append(Text(alias, DtshTui.style(DtshTui.STYLE_DT_ALIAS)))
        txt = Text(' ').join(txt_aliases)
        if with_status and (node.status != 'okay'):
            DtshTui.txt_dim(txt)
        return txt

    @staticmethod
    def mk_txt_node_desc_short(node: Node,
                               with_link: bool = True,
                               with_status: bool = False) -> Text:
        txt = DtshTui.mk_txt_desc_short(node.description)
        if with_link and node.binding_path:
            if not node.matching_compat:
                # Nodes may have a binding without a matching compat: set
                # the link on the description
                DtshTui.txt_update_link_file(txt, node.binding_path)
        if with_status and (node.status != 'okay'):
            DtshTui.txt_dim(txt)
        return txt

    @staticmethod
    def mk_txt_node_all_labels(node: Node, with_status: bool = False) -> Text:
        txt = DtshTui.mk_txt_node_label(node, with_status=with_status)
        if len(txt.plain) > 0:
            txt.append_text(Text(', ', DtshTui.style(DtshTui.STYLE_DEFAULT)))
        txt.append_text(DtshTui.mk_txt_node_labels(node, with_status=with_status))
        return txt

    @staticmethod
    def mk_txt_binding(binding: Binding, with_link: bool = True) -> Text:
        if not binding.compatible:
            return Text()
        txt = Text(binding.compatible, DtshTui.style(DtshTui.STYLE_DT_BINDING))
        if binding.path and with_link:
            DtshTui.txt_update_link_file(txt, binding.path)
        return txt

    @staticmethod
    def mk_txt_reg_size(reg: Register) -> Text:
        if reg.size is None:
            return Text()
        return Text(str(reg.size))

    @staticmethod
    def mk_txt_reg_end_addr(reg: Register) -> Text:
        if reg.size is None:
            return Text()
        return Text(hex(reg.addr + reg.size - 1))

    @staticmethod
    def mk_txt_reg_name(reg: Register) -> Text:
        if reg.name is None:
            return Text()
        return Text(reg.name)

    @staticmethod
    def mk_txt_prop_last_binding(prop_spec: PropertySpec,
                                 with_link: bool = True) -> Text:
        if not prop_spec.path:
            return Text()
        txt = Text(os.path.basename(prop_spec.path),
                   DtshTui.style(DtshTui.STYLE_DT_BINDING))
        if prop_spec.path and with_link:
            DtshTui.txt_update_link_file(txt, prop_spec.path)
        return txt

    @staticmethod
    def mk_txt_prop_desc(prop: Property) -> Text:
        if prop.spec and prop.spec.description:
            txt = DtshTui.mk_txt_desc(prop.spec.description)
        else:
            txt = Text("No description available.",
                       DtshTui.style(DtshTui.STYLE_APOLOGY))
        return txt

    @staticmethod
    def mk_txt_prop_value(prop: Property) -> Text:
        return DtshTui.mk_txt_dt_value(prop.val, prop.type)

    @staticmethod
    def mk_txt_dt_value(dt_val: object, dt_type: str) -> Text:
        if dt_type in ['phandle', 'path']:
            # prop value is the pointed Node
            return Text(dt_val.name)
        elif dt_type == 'boolean':
            return DtshTui.mk_txt_bool(dt_val)
        elif dt_type == 'phandles':
            # prop value is a list of pointed Node
            names = [node.name for node in dt_val]
            return Text(str(names))
        elif dt_type == 'phandle-array':
            # prop value is a list of ControllerAndData
            # controller is a Node
            controllers = [cad.controller.name for cad in dt_val]
            return Text(str(controllers))
        return Text(str(dt_val))


    ############################################################################
    # Layouts: DT objects
    ############################################################################

    @staticmethod
    def mk_form_node_common(node: Node, shell: Dtsh) -> Table:
        form = DtshTui.mk_form()
        form.add_row('Path:', node.path)
        form.add_row('Name:', DtshTui.get_node_nick(node))
        if node.unit_addr is not None:
            form.add_row('Unit address:', DtshTui.mk_txt_node_addr(node))
        if node.compats:
            form.add_row('Compatible:', DtshTui.mk_txt_node_compats(node, shell))
        if node.label:
            form.add_row('Label:', DtshTui.mk_txt_node_label(node))
        if node.labels:
            form.add_row('Labels:', DtshTui.mk_txt_node_labels(node))
        if node.aliases:
            form.add_row('Aliases:', DtshTui.mk_txt_node_aliases(node))
        form.add_row('Status:', DtshTui.mk_txt_node_status(node))
        return form

    @staticmethod
    def mk_grid_node_depends_on(node: Node) -> Table:
        if node.depends_on:
            grid = DtshTui.mk_grid(2)
            for node in node.depends_on:
                grid.add_row(node.name, DtshTui.mk_txt_node_binding(node))
        else:
            grid = DtshTui.mk_grid(1)
            grid.add_row(Text("This node does not directly depend on any node.",
                              DtshTui.style(DtshTui.STYLE_APOLOGY)))
        return grid

    @staticmethod
    def mk_grid_node_required_by(node: Node) -> Table:
        if node.required_by:
            grid = DtshTui.mk_grid(2)
            for node in node.required_by:
                grid.add_row(node.name, DtshTui.mk_txt_node_binding(node))
        else:
            grid = DtshTui.mk_grid(1)
            grid.add_row(Text("There's no other node that directly depends on this node.",
                              DtshTui.style(DtshTui.STYLE_APOLOGY)))
        return grid

    @staticmethod
    def mk_grid_node_registers(node: Node) -> Table:
        if node.regs:
            grid = DtshTui.mk_grid_simple_head(
                ['Address', 'Size', 'End', 'Name']
            )
            for reg in node.regs:
                grid.add_row(Text(hex(reg.addr)),
                             DtshTui.mk_txt_reg_size(reg),
                             DtshTui.mk_txt_reg_end_addr(reg),
                             DtshTui.mk_txt_reg_name(reg))
        else:
            grid = DtshTui.mk_grid(1)
            grid.add_row(Text("This node does not define any register.",
                              DtshTui.style(DtshTui.STYLE_APOLOGY)))
        return grid

    @staticmethod
    def mk_grid_node_properties(node: Node) -> Table:
        if node.props:
            grid = DtshTui.mk_grid_simple_head(['Name', 'Type', 'Value'])
            for _, prop in node.props.items():
                grid.add_row(prop.name,
                             prop.type,
                             DtshTui.mk_txt_prop_value(prop))
        else:
            grid = DtshTui.mk_grid(1)
            grid.add_row(Text("This node does not define any property.",
                              DtshTui.style(DtshTui.STYLE_APOLOGY)))
        return grid

    @staticmethod
    def mk_form_prop_spec(prop:Property) -> Table:
        form = DtshTui.mk_form()
        form.add_row('Name:', prop.name)
        form.add_row('Type:', prop.type)
        form.add_row('Required:', DtshTui.mk_txt_bool(prop.spec.required))
        form.add_row('Value:', DtshTui.mk_txt_prop_value(prop))
        if prop.spec.path:
            form.add_row('From:', DtshTui.mk_txt_prop_last_binding(prop.spec))
        if prop.spec.default:
            form.add_row('Default:',
                         DtshTui.mk_txt_dt_value(prop.spec.default, prop.type))
        return form

    @staticmethod
    def mk_form_prop_name_val(prop:Property) -> Table:
        form = DtshTui.mk_form()
        form.add_row('Name:', prop.name)
        form.add_row('Value:', DtshTui.mk_txt_prop_value(prop))
        return form

    @staticmethod
    def mk_node_tree_item(node: Node,
                          shell: Dtsh,
                          width: list[int],
                          with_status: bool = False) -> Table:
        grid = DtshTui.mk_grid(3)
        for i, w in enumerate(width):
            if w > 0:
                grid.columns[i].width = w
        grid.add_row(
            DtshTui.mk_txt_node_addr(node, with_status=with_status),
            DtshTui.mk_txt_node_nick(node, with_status=with_status),
            DtshTui.mk_txt_node_compats(node, shell, with_status=with_status)
        )
        return grid

    ############################################################################
    # Layouts: yaml
    ############################################################################

    @staticmethod
    def mk_yaml(path: str, theme: str = 'ansi_dark') -> Syntax:
        return Syntax.from_path(path, lexer='yaml', theme=theme,)

    @staticmethod
    def mk_yaml_node_binding(node: Node) -> RenderableType:
        if not node.binding_path:
            return Text("No binding source available.",
                        DtshTui.style(DtshTui.STYLE_APOLOGY))
        grid = DtshTui.mk_grid(1)
        txt_path = Text(os.path.basename(node.binding_path))
        DtshTui.txt_update_link_file(txt_path, node.binding_path)
        grid.add_row(txt_path)
        grid.add_row(None)
        grid.add_row(DtshTui.mk_yaml(node.binding_path))
        return grid

    @staticmethod
    def mk_yaml_prop_binding(prop: Property) -> RenderableType:
        if not (prop.spec and prop.spec.binding and prop.spec.binding.path):
            return Text("No binding source available.",
                        DtshTui.style(DtshTui.STYLE_APOLOGY))
        grid = DtshTui.mk_grid(1)
        txt_path = Text(os.path.basename(prop.spec.binding.path))
        DtshTui.txt_update_link_file(txt_path, prop.spec.binding.path)
        grid.add_row(txt_path)
        grid.add_row(None)
        grid.add_row(DtshTui.mk_yaml(prop.spec.binding.path))
        return grid


    ############################################################################
    # Layouts: base
    ############################################################################

    @staticmethod
    def mk_grid(cols: int) -> Table:
        grid = Table.grid(padding=(0, 1))
        for _ in range(0, cols):
            grid.add_column()
        return grid

    @staticmethod
    def mk_form(name_style: Style | None = None,
                value_style: Style | None = None ) -> Table:
        form = DtshTui.mk_grid(2)
        if name_style:
            form.columns[0].style = name_style
        if value_style:
            form.columns[1].style = value_style
        return form

    @staticmethod
    def form_add(form: Table, name: str, val: str):
        form.add_row(name, val)

    @staticmethod
    def mk_grid_simple_head(cols: list[str]) -> Table:
        grid = Table.grid(padding=(0, 1))
        grid.box = box.SIMPLE_HEAD
        grid.show_header = True
        grid.header_style = DtshTui.style(DtshTui.STYLE_DEFAULT)
        for header in cols:
            grid.add_column(header=header)
        return grid


    ############################################################################
    # Internals
    ############################################################################

    @staticmethod
    def _load_theme() -> Theme:
        theme = None
        theme_path = os.path.join(Dtsh.cfg_dir_path(), 'theme')
        if os.path.isfile(theme_path):
            try:
                theme = Theme.from_file(open(theme_path))
            except Exception:
                pass
        if not theme:
            theme_path = os.path.join(os.path.dirname(__file__), 'theme')
            theme = Theme.from_file(open(theme_path))
        return theme


############################################################################
# Views
############################################################################

class DtshTuiView(object):
    """
    """
    _view: RenderableType

    def show(self, vt: DtshVt, with_pager: bool = False):
        """
        """
        if with_pager:
            vt.pager_enter()
        vt.write(self._view)
        if with_pager:
            vt.pager_exit()

class DtshTuiStructuredView(DtshTuiView):
    """
    """

    def __init__(self) -> None:
        super().__init__()
        self._view = DtshTui.mk_grid(2)

    def add_section(self, label: str, v_section: RenderableType):
        txt_label = Text(label, DtshTui.style('bold'))
        self._as_grid().add_row(txt_label, None)
        self._as_grid().add_row(None, v_section)
        self._as_grid().add_row(None, None)

    def _as_grid(self) -> Table:
        return self._view

class DtNodeView(DtshTuiStructuredView):
    """
    """

    def __init__(self, node:Node, shell:Dtsh) -> None:
        super().__init__()
        self.add_section('Node',
                         DtshTui.mk_form_node_common(node, shell))
        self.add_section('Description',
                         DtshTui.mk_txt_desc(node.description))
        self.add_section('Depends-on',
                         DtshTui.mk_grid_node_depends_on(node))
        self.add_section('Required-by',
                         DtshTui.mk_grid_node_required_by(node))
        self.add_section('Registers',
                         DtshTui.mk_grid_node_registers(node))
        self.add_section('Properties',
                         DtshTui.mk_grid_node_properties(node))
        self.add_section('Binding',
                         DtshTui.mk_yaml_node_binding(node))

class DtPropertyView(DtshTuiStructuredView):
    """
    """
    def __init__(self, prop:Property) -> None:
        super().__init__()
        if prop.spec:
            self.add_section('Property', DtshTui.mk_form_prop_spec(prop))
            self.add_section('Description', DtshTui.mk_txt_prop_desc(prop))
            self.add_section('Binding',
                             DtshTui.mk_yaml_prop_binding(prop))
        else:
            self.add_section('Property',
                             DtshTui.mk_form_prop_name_val(prop))

class DtNodeListView(DtshTuiView):
    """
    """

    def __init__(self,
                 node_map: dict[str, list[Node]],
                 shell: Dtsh,
                 with_no_content: bool = False,
                 with_rich_fmt: bool = False) -> None:
        super().__init__()
        if with_rich_fmt:
            self._init_rich_view(node_map, shell, with_no_content)
        else:
            self._init_default_view(node_map, with_no_content)

    def _init_default_view(self,
                           node_map: dict[str, list[Node]],
                           with_no_content: bool):
        self._view = DtshTui.mk_grid(1)
        N = len(node_map)
        n = 0
        for path, nodes in node_map.items():
            if with_no_content:
                self._view.add_row(f'{path}')
            else:
                if N > 1:
                    self._view.add_row(f'{path}:')
                for node in nodes:
                    self._view.add_row(f'{node.path}')
                if n < (N - 1):
                    self._view.add_row(None)
                n += 1

    def _init_rich_view(self,
                        node_map: dict[str, list[Node]],
                        shell: Dtsh,
                        with_no_content: bool):
        if with_no_content:
            self._view = self._mk_node_grid()
            for path, _ in node_map.items():
                node = shell.path2node(path)
                self._grid_add_node_row(self._view, node, shell)
        else:
            self._view = DtshTui.mk_grid(1)
            N = len(node_map)
            n = 0
            for path, content in node_map.items():
                self._view.add_row(Text(f"{path}:", DtshTui.style('bold')))
                if content:
                    v_content = self._mk_node_grid()
                    for node in content:
                        self._grid_add_node_row(v_content, node, shell)
                    self._view.add_row(v_content)
                if n < (N - 1):
                    self._view.add_row(None)
                n += 1

    def _mk_node_grid(self):
        return DtshTui.mk_grid_simple_head(
            [
                'Name', 'Address', 'Labels', 'Aliases', 'Compatible', 'Description'
            ]
        )

    def _grid_add_node_row(self, grid:Table, node: Node, shell: Dtsh):
        grid.add_row(
            DtshTui.mk_txt_node_nick(node, with_status=True),
            DtshTui.mk_txt_node_addr(node, with_status=True),
            DtshTui.mk_txt_node_all_labels(node, with_status=True),
            DtshTui.mk_txt_node_aliases(node, with_status=True),
            DtshTui.mk_txt_node_compats(node, shell, with_status=True),
            DtshTui.mk_txt_node_desc_short(node, with_status=True),
        )


class DtNodeTreeView(DtshTuiView):
    """
    """

    def __init__(self,
                 root: Node,
                 shell: Dtsh,
                 level: int,
                 with_rich_fmt: bool) -> None:
        super().__init__()
        self._rich_fmt = with_rich_fmt
        self._dtsh = shell
        self._level = level
        self._depth = 0

        anchor = Text(root.path, DtshTui.style('bold'))
        self._view = Tree(anchor)
        self._follow_node_branch(root, self._view)

    def _follow_node_branch(self,
                            root: Node,
                            tree: Tree) -> None:
        # Increase depth when following a branch.
        self._depth += 1

        # Maximum length of child nodes nickname.
        width = self._get_branch_width(root)

        for _, node in root.children.items():
            if self._rich_fmt:
                anchor = DtshTui.mk_node_tree_item(node, self._dtsh, width, True)
            else:
                anchor = node.name
            branch = tree.add(anchor)

            if (self._level == 0) or (self._depth < self._level):
                if node.status != 'disabled':
                    self._follow_node_branch(node, branch)

        # Decrease depth on return.
        self._depth -= 1

    def _get_branch_width(self, root: Node) -> list[int]:
        width_addr = 0
        width_nick = 0
        for _, node in root.children.items():
            nick = DtshTui.get_node_nick(node)
            w = len(nick)
            if w > width_nick:
                width_nick = w
            w = len(DtshTui.mk_txt_node_addr(node).plain)
            if w > width_addr:
                width_addr = w
        return [width_addr, width_nick]