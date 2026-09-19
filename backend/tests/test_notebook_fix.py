"""Feature 8 slice 1: notebook crash fix pinned (hermetic)."""


def test_autofolder_saves_single_notebook():
    import inspect
    import routers.notebooks as nb
    src = inspect.getsource(nb.ai_autofolder_all)
    assert "_save_notebooks()" not in src
    assert "_save_notebook(notebook)" in src


def test_notebook_service_has_single_save():
    from services.notebook_service import NotebookService
    assert hasattr(NotebookService, "_save_notebook")
