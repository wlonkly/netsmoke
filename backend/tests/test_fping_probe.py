from netsmoke.probes.fping import FPingProbe



def test_parse_output_reads_latency_samples_and_losses() -> None:
    output = '''
    1.1.1.1 : 11.2 10.8 - 12.4
    8.8.8.8 : - - - -
    '''

    parsed = FPingProbe.parse_output(output, hosts=['1.1.1.1', '8.8.8.8'], count=4)

    assert parsed['1.1.1.1'] == [11.2, 10.8, None, 12.4]
    assert parsed['8.8.8.8'] == [None, None, None, None]
