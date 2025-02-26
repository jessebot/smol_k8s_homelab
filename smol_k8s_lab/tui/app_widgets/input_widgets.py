# smol-k8s-lab libraries
from smol_k8s_lab.tui.util import placeholder_grammar, create_sanitized_list
from smol_k8s_lab.utils.value_from import extract_secret

# external libraries
from ruamel.yaml import CommentedSeq
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal
from textual.validation import Length
from textual.widgets import Input, Label, Static, Collapsible, Button, Switch


class SmolK8sLabCollapsibleInputsWidget(Static):
    """
    widget for input fields for an app
    for argocd that are passed to the argocd appset secrets plugin helm chart
    """
    BINDINGS = [Binding(key="b,escape,q",
                        key_display="b",
                        action="app.pop_screen",
                        description=" Back")]

    def __init__(self,
                 app_name: str,
                 title: str,
                 collapsible_id: str,
                 inputs: dict = {},
                 tooltips: dict = {},
                 add_fields_button: bool = False) -> None:

        self.app_name = app_name
        self.title = title
        self.inputs = inputs
        self.tooltips = tooltips
        self.add_fields_button = add_fields_button
        self.collapsible_id = collapsible_id

        super().__init__()

    def compose(self) -> ComposeResult:
        with Collapsible(collapsed=False, title=self.title, id=self.collapsible_id):
            if self.inputs:
                yield Grid(classes="collapsible-updateable-grid")

    def on_mount(self) -> None:
        """
        update the grid for all new inputs
        """
        grid = self.query_one(".collapsible-updateable-grid")

        if self.inputs:
            for key, value in self.inputs.items():
                grid.mount(self.generate_row(key, value))

        if self.add_fields_button:
            grid.mount(Button("➕ new field"))

    def generate_row(self, key: str, value: str | bool) -> Grid | Horizontal:
        # if key == 'create_minio_tenant':
        #     return self.generate_switch_row(key, value)
        return self.generate_input_row(key, value)

    def generate_switch_row(self, key: str, value: bool) -> Horizontal:
        tooltip = "enable the use of a local minio tenant using the minio operator"
        switch = Switch(value=value,
                        classes="bool-switch-row-switch",
                        name=key,
                        id=f"{self.app_name}-minio-tenant")
        switch.tooltip = tooltip

        bool_label = Label("Create MinIO tenant:", classes="argo-config-label")
        bool_label.tooltip = tooltip

        return Horizontal(bool_label, switch, classes="argo-switch-row")

    def generate_input_row(self, key: str, value: str = "") -> Grid:
        """
        add a new row of keys to pass to an argocd app
        """
        key_label = key.replace("_", " ")

        # create input
        placeholder_txt = placeholder_grammar(key_label)
        input_keys = {"placeholder": placeholder_txt,
                      "name": key,
                      "id": "-".join([self.app_name, key, "input"]),
                      "validators": [Length(minimum=2)]}

        # only give an initial value if one was found in the yaml or env var
        if value:
            # handle ruamel commented sequence (dict from yaml with comments)
            if isinstance(value, CommentedSeq) or isinstance(value, list):
                if isinstance(value[0], str):
                    sequence_value = ", ".join(value)

                elif isinstance(value[0], list):
                    # we grab value[0] because ruamel.yaml's CommentedSeq is weird
                    sequence_value = ", ".join(value[0])

                # reassign value if this is a CommentedSeq for validation later on
                value = sequence_value
                input_keys['password'] = False

            # otherwise this is a sensitive value, and we have to get it externally
            elif isinstance(value, dict):
                input_keys['password'] = True
                value = extract_secret(value)
            # this is probably just a plain text string
            else:
                input_keys['password'] = False

            input_keys["value"] = value

        # add all the input_keys dictionary as args to Input widget
        input = Input(**input_keys)

        # make sure Input widget has a tooltip
        tooltip = self.tooltips.get(key, None)
        if not tooltip:
            if input_keys['password']:
                env_var = "_".join([self.app_name.upper(), key.upper()])
                tooltip = (f"To avoid needing to fill in this value manually, you"
                           f" can export ${env_var} as an environment variable.")
            else:
                if key == "s3_provider":
                    tooltip = "Choose between minio and seaweedfs for a local s3 provider"
                else:
                    tooltip = placeholder_txt + "."

        # special metallb tooltip
        if self.app_name == "metallb":
            tooltip += (" Be sure the ip addresses you enter already have DNS "
                        "entries for any apps you'd like to deploy.")

        input.tooltip = tooltip

        # immediately validate to get a pink border if input value is invalid
        input.validate(value)

        # create and return the Label + Input row
        return Grid(Label(f"{key_label}:", classes="input-label"),
                    input,
                    classes="app-input-row")

    @on(Input.Changed)
    def input_validation(self, event: Input.Changed) -> None:
        if event.validation_result.is_valid:
            input = event.input
            parent_yaml = self.app.cfg['apps'][self.app_name]['init']['values']

            if event.validation_result.is_valid:
                # this checks if this is a sensitive input
                password = input.password

                if self.app_name in ["metallb", "vouch"] or "," in input.value:
                    parent_yaml[input.name] = create_sanitized_list(input.value)
                else:
                    if not password:
                        parent_yaml[input.name] = input.value

                # if this is a plain text value, write the yaml
                if not input.password:
                    self.app.write_yaml()
                # else, save it to a special place
                else:
                    self.log(f"saving special value for {input.name} to screen cache")
                    self.screen.sensitive_values[self.app_name][input.name] = input.value
        else:
            if self.app.bell_on_error:
                self.app.bell()
            # if result is not valid, notify the user why
            self.notify("\n".join(event.validation_result.failure_descriptions),
                        severity="warning",
                        title="⚠️ Input Validation Error\n")

    @on(Switch.Changed)
    def update_base_yaml_for_switch(self, event: Switch.Changed) -> None:
        """
        if user changes a boolean init value, we write that out
        """
        truthy = event.value
        self.app.cfg['apps'][self.app_name]['init'][event.switch.name] = truthy
        self.app.write_yaml()

        if truthy and event.switch.name == "create_minio_tenant":
            self.app.notify("💡Make sure Argo CD directory recursion is switched on.")


class SmolK8sLabInputsWidget(Static):
    """
    widget for input fields for an app
    for argocd that are passed to the argocd appset secrets plugin helm chart
    """
    BINDINGS = [Binding(key="b,escape,q",
                        key_display="b",
                        action="app.pop_screen",
                        description=" Back")]

    def __init__(self,
                 app_name: str,
                 title: str,
                 id: str,
                 inputs: dict = {},
                 tooltips: dict = {},
                 add_fields_button: bool = False) -> None:

        self.app_name = app_name
        self.title = title
        self.inputs = inputs
        self.tooltips = tooltips
        self.add_fields_button = add_fields_button

        super().__init__(id=id)

    def compose(self) -> ComposeResult:
        yield Label(self.title, classes="header-row")
        yield Grid(classes="collapsible-updateable-grid")

    def on_mount(self) -> None:
        """
        update the grid for all new inputs
        """
        grid = self.query_one(".collapsible-updateable-grid")

        if self.inputs:
            for key, value in self.inputs.items():
                # ignore this particular key
                if key != "trusted_key_servers":
                    grid.mount(self.generate_row(key, value))

        if self.add_fields_button:
            grid.mount(Button("➕ new field"))

    def generate_row(self, key: str, value: str | bool) -> Grid | Horizontal:
        # if key == 'create_minio_tenant':
        #     return self.generate_switch_row(key, value)
        return self.generate_input_row(key, value)

    def generate_switch_row(self, key: str, value: bool) -> Horizontal:
        tooltip = "enable the use of a local minio tenant using the minio operator"
        switch = Switch(value=value,
                        classes="bool-switch-row-switch",
                        name=key,
                        id=f"{self.app_name}-minio-tenant")
        switch.tooltip = tooltip

        bool_label = Label("Create MinIO tenant:", classes="argo-config-label")
        bool_label.tooltip = tooltip

        return Horizontal(bool_label, switch, classes="argo-switch-row")

    def generate_input_row(self, key: str, value: str = "") -> Grid:
        """
        add a new row of keys to pass to an argocd app
        """
        key_label = key.replace("_", " ")

        # create input
        placeholder_txt = placeholder_grammar(key_label)
        input_keys = {"placeholder": placeholder_txt,
                      "name": key,
                      "id": "-".join([self.app_name, key, "input"]),
                      "password": False,
                      "validators": [Length(minimum=2)]}

        # only give an initial value if one was found in the yaml or env var
        if value:
            # handle ruamel commented sequence (dict from yaml with comments)
            if isinstance(value, CommentedSeq) or isinstance(value, list):
                if isinstance(value[0], str):
                    sequence_value = ", ".join(value)

                elif isinstance(value[0], list):
                    # we grab value[0] because ruamel.yaml's CommentedSeq is weird
                    sequence_value = ", ".join(value[0])

                # reassign value if this is a CommentedSeq for validation later on
                value = sequence_value

            # otherwise this is a sensitive value, and we have to get it externally
            elif isinstance(value, dict):
                input_keys['password'] = True
                value = extract_secret(value)

        # add all the input_keys dictionary as args to Input widget
        input_keys['value'] = value
        input = Input(**input_keys)

        # make sure Input widget has a tooltip
        tooltip = self.tooltips.get(key, None)
        if not tooltip:
            if input_keys['password']:
                env_var = "_".join([self.app_name.upper(), key.upper()])
                tooltip = (f"To avoid needing to fill in this value manually, you"
                           f" can export ${env_var} as an environment variable.")
            else:
                if key == "s3_provider":
                    tooltip = "Choose between minio and seaweedfs for a local s3 provider"
                else:
                    tooltip = placeholder_txt + "."

        # special metallb tooltip
        if self.app_name == "metallb":
            tooltip += (" Be sure the ip addresses you enter already have DNS "
                        "entries for any apps you'd like to deploy.")

        input.tooltip = tooltip

        # immediately validate to get a pink border if input value is invalid
        input.validate(value)

        # create and return the Label + Input row
        return Grid(Label(f"{key_label}:", classes="input-label"),
                    input,
                    classes="app-input-row")

    @on(Input.Changed)
    def input_validation(self, event: Input.Changed) -> None:
        if event.validation_result.is_valid:
            input = event.input
            parent_yaml = self.app.cfg['apps'][self.app_name]['init']['values']

            if event.validation_result.is_valid:
                # this checks if this is a sensitive input
                password = input.password

                if self.app_name in ["metallb", "vouch"] or "," in input.value:
                    parent_yaml[input.name] = create_sanitized_list(input.value)
                else:
                    if not password:
                        parent_yaml[input.name] = input.value

                # if this is a plain text value, write the yaml
                if not input.password:
                    self.app.write_yaml()
                # else, save it to a special place
                else:
                    self.log(f"saving special value for {input.name} to screen cache")
                    self.screen.sensitive_values[self.app_name][input.name] = input.value
        else:
            if self.app.bell_on_error:
                self.app.bell()
            # if result is not valid, notify the user why
            self.notify("\n".join(event.validation_result.failure_descriptions),
                        severity="warning",
                        title="⚠️ Input Validation Error\n")

    @on(Switch.Changed)
    def update_base_yaml_for_switch(self, event: Switch.Changed) -> None:
        """
        if user changes a boolean init value, we write that out
        """
        truthy = event.value
        self.app.cfg['apps'][self.app_name]['init'][event.switch.name] = truthy
        self.app.write_yaml()

        if truthy and event.switch.name == "create_minio_tenant":
            self.app.notify("💡Make sure Argo CD directory recursion is switched on.")
