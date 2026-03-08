"""Tests for pinger.py"""

import asyncio

import pytest

from netsmoke.pinger import parse_fping_output, ping_hosts


def test_parse_basic_output():
    output = "8.8.8.8 : 12.34 11.23 13.01\n"
    result = parse_fping_output(output, ["8.8.8.8"])
    assert result["8.8.8.8"] == [12.34, 11.23, 13.01]


def test_parse_packet_loss():
    output = "1.1.1.1 : 10.00 - 10.01 -\n"
    result = parse_fping_output(output, ["1.1.1.1"])
    assert result["1.1.1.1"] == [10.00, None, 10.01, None]


def test_parse_all_loss():
    output = "9.9.9.9 : - - - - -\n"
    result = parse_fping_output(output, ["9.9.9.9"])
    assert result["9.9.9.9"] == [None, None, None, None, None]


def test_parse_multiple_hosts():
    output = (
        "8.8.8.8 : 12.34 11.23\n"
        "1.1.1.1 : 10.00 9.99\n"
    )
    result = parse_fping_output(output, ["8.8.8.8", "1.1.1.1"])
    assert result["8.8.8.8"] == [12.34, 11.23]
    assert result["1.1.1.1"] == [10.00, 9.99]


def test_missing_host_filled_empty():
    """Hosts not in output get an empty list (all-loss interpretation)."""
    output = "8.8.8.8 : 12.34\n"
    result = parse_fping_output(output, ["8.8.8.8", "1.1.1.1"])
    assert result["1.1.1.1"] == []


def test_parse_empty_output():
    result = parse_fping_output("", ["8.8.8.8"])
    assert result["8.8.8.8"] == []


def test_parse_ignores_non_matching_lines():
    output = (
        "ICMP Host Unreachable from ...\n"
        "8.8.8.8 : 12.34 11.23\n"
    )
    result = parse_fping_output(output, ["8.8.8.8"])
    assert result["8.8.8.8"] == [12.34, 11.23]


def test_parse_whitespace_tolerance():
    output = "  8.8.8.8 : 12.34  11.23  \n"
    result = parse_fping_output(output, ["8.8.8.8"])
    assert result["8.8.8.8"] == [12.34, 11.23]


@pytest.mark.asyncio
async def test_ping_hosts_empty_list():
    """ping_hosts returns {} immediately for an empty host list without invoking fping."""
    result = await ping_hosts([])
    assert result == {}


@pytest.mark.asyncio
async def test_ping_hosts_fping_not_found(monkeypatch):
    """ping_hosts raises RuntimeError when the fping binary is not on PATH."""
    async def mock_exec(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(asyncio, "create_subprocess_exec", mock_exec)

    with pytest.raises(RuntimeError, match="fping not found"):
        await ping_hosts(["8.8.8.8"])
