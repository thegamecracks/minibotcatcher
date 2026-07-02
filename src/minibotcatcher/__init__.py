def _get_version() -> str:
    from importlib.metadata import version

    return version(_dist_name)


_dist_name = "minibotcatcher"
__version__ = _get_version()
