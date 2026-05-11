import os


def test_sharedclientcache_files_to_delete_preserves_mcp_by_default():
    import qoder_reset_gui

    os.environ.pop("QODER_CLEAN_MCP_JSON", None)
    files = qoder_reset_gui._sharedclientcache_files_to_delete(preserve_model_settings=True)
    assert "mcp.json" not in files


def test_sharedclientcache_files_to_delete_can_delete_mcp_when_requested():
    import qoder_reset_gui

    os.environ.pop("QODER_CLEAN_MCP_JSON", None)
    files = qoder_reset_gui._sharedclientcache_files_to_delete(preserve_model_settings=False)
    assert "mcp.json" in files


def test_sharedclientcache_files_to_delete_env_override():
    import qoder_reset_gui

    old = os.environ.get("QODER_CLEAN_MCP_JSON")
    try:
        os.environ["QODER_CLEAN_MCP_JSON"] = "1"
        files = qoder_reset_gui._sharedclientcache_files_to_delete(preserve_model_settings=True)
        assert "mcp.json" in files
    finally:
        if old is None:
            os.environ.pop("QODER_CLEAN_MCP_JSON", None)
        else:
            os.environ["QODER_CLEAN_MCP_JSON"] = old

