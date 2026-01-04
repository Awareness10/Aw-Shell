import webbrowser

from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.label import Label

from config.data import APP_NAME_CAP


def build_about_tab() -> Box:
    vbox = Box(orientation="v", spacing=18, style="margin: 30px;")

    vbox.add(
        Label(
            markup=f"<b>{APP_NAME_CAP}</b>",
            h_align="start",
            style="font-size: 1.5em; margin-bottom: 8px;",
        )
    )

    vbox.add(
        Label(
            label="A hackable shell for Hyprland, powered by Fabric.",
            h_align="start",
            style="margin-bottom: 12px;",
        )
    )

    repo_box = Box(orientation="h", spacing=6, h_align="start")
    repo_label = Label(label="GitHub:", h_align="start")
    repo_link = Label(
        markup='<a href="https://github.com/awareness10/Aw-Shell">https://github.com/awareness10/Aw-Shell</a>'
    )
    repo_box.add(repo_label)
    repo_box.add(repo_link)
    vbox.add(repo_box)

    original_box = Box(orientation="h", spacing=6, h_align="start")
    original_label = Label(label="Original:", h_align="start")
    original_link = Label(
        markup='<a href="https://github.com/Axenide/Ax-Shell">Axenide/Ax-Shell</a>'
    )
    original_box.add(original_label)
    original_box.add(original_link)
    vbox.add(original_box)

    def on_kofi_clicked(_):
        webbrowser.open("https://ko-fi.com/Axenide")

    kofi_btn = Button(
        label="Support Original Author on Ko-Fi",
        on_clicked=on_kofi_clicked,
        tooltip_text="Support Axenide on Ko-Fi",
        style="margin-top: 18px; min-width: 160px;",
    )
    vbox.add(kofi_btn)
    vbox.add(Box(v_expand=True))

    return vbox
