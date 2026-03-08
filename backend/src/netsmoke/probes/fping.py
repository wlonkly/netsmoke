from __future__ import annotations

import asyncio
from collections.abc import Sequence


class ProbeExecutionError(RuntimeError):
    pass


class FPingProbe:
    def __init__(self, binary: str = 'fping') -> None:
        self.binary = binary

    async def run(
        self,
        hosts: Sequence[str],
        *,
        count: int,
        timeout_seconds: float,
        packet_size_bytes: int,
    ) -> dict[str, list[float | None]]:
        if not hosts:
            return {}

        command = [
            self.binary,
            '-C',
            str(count),
            '-q',
            '-B1',
            '-r1',
            '-t',
            str(int(timeout_seconds * 1000)),
            '-b',
            str(packet_size_bytes),
            *hosts,
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise ProbeExecutionError(f'fping binary not found: {self.binary}') from exc

        stdout, stderr = await process.communicate()
        output = '\n'.join(part.decode().strip() for part in (stdout, stderr) if part).strip()

        if process.returncode not in (0, 1):
            raise ProbeExecutionError(output or f'fping exited with status {process.returncode}')

        return self.parse_output(output, hosts=hosts, count=count)

    @staticmethod
    def parse_output(output: str, *, hosts: Sequence[str], count: int) -> dict[str, list[float | None]]:
        parsed: dict[str, list[float | None]] = {host: [None] * count for host in hosts}

        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line or ':' not in line:
                continue

            host, separator, values = line.partition(' : ')
            if not separator:
                host, separator, values = line.partition(':')
            host = host.strip()
            if host not in parsed:
                continue

            samples: list[float | None] = []
            for token in values.strip().split():
                if token == '-':
                    samples.append(None)
                    continue

                try:
                    samples.append(float(token))
                except ValueError:
                    continue

            if samples:
                parsed[host] = (samples + [None] * count)[:count]

        return parsed
