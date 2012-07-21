#!/usr/bin/env python

#
# Transmitter of IEEE 802.15.4 RADIO Packets.
#
# Modified by: Thomas Schmid, Sanna Leidelof
#

from gnuradio import gr, eng_notation
from uhd_interface import uhd_transmitter
from gnuradio import ucla
from gnuradio.ucla_blks import ieee802_15_4_pkt
from gnuradio.eng_option import eng_option
from optparse import OptionParser
import math, struct, time

# insert this in your test code...
#import os
#print 'Blocked waiting for GDB attach (pid = %d)' % (os.getpid(),)
#raw_input ('Press Enter to continue: ')

class transmit_path(gr.top_block):
    def __init__(self, options):
        gr.top_block.__init__(self)

        if options.outfile is not None:
          u = gr.file_sink(gr.sizeof_gr_complex, options.outfile)
        elif (options.tx_freq is not None) or (options.channel is not None):
          if options.channel is not None:
            self.chan_num = options.channel
            options.tx_freq = ieee802_15_4_pkt.chan_802_15_4.chan_map[self.chan_num]

          u = uhd_transmitter(options.tx_args,
                              options.bandwidth,
                              options.tx_freq, options.tx_gain,
                              options.spec, options.antenna,
                              options.verbose, options.external)
        else:
          raise SystemExit("--tx-freq, --channel or --outfile must be specified\n")

        self.samples_per_symbol = 2

        # transmitter
        self.packet_transmitter = ieee802_15_4_pkt.ieee802_15_4_mod_pkts(self,
                spb=self.samples_per_symbol, msgq_limit=2, log=options.log)
        self.amp = gr.multiply_const_cc(1)

        self.u = u
        self.connect(self.packet_transmitter, self.amp, self.u)

        self.connect(self.amp, gr.file_sink(gr.sizeof_gr_complex, 'cc2420-tx-diag.dat'))


    def send_pkt(self, payload='', eof=False):
        return self.packet_transmitter.send_pkt(0xe5, struct.pack("HHHH", 0xFFFF, 0xFFFF, 0x10, 0x10), payload, eof)

    def add_options(normal, expert):
        """
        Adds usrp-specific options to the Options Parser
        """
        normal.add_option("", "--outfile", type="string",
                          help="select output file to modulate to")
        normal.add_option ("-c", "--channel", type="eng_float", default=17,
                          help="Set 802.15.4 Channel to listen on channel %default", metavar="FREQ")
        normal.add_option("", "--amp", type="eng_float", default=1, metavar="AMPL",
                          help="set transmitter digital amplifier: [default=%default]")
        normal.add_option("-v", "--verbose", action="store_true", default=False)
        normal.add_option("-W", "--bandwidth", type="eng_float",
                          default=4000e3,
                          help="set symbol bandwidth [default=%default]")
        expert.add_option("", "--log", action="store_true", default=False,
                          help="Log all parts of flow graph to files (CAUTION: lots of data)")
        uhd_transmitter.add_options(normal)

    # Make a static method to call before instantiation
    add_options = staticmethod(add_options)

# /////////////////////////////////////////////////////////////////////////////
#                                   main
# /////////////////////////////////////////////////////////////////////////////
def main ():
    parser = OptionParser (option_class=eng_option, conflict_handler="resolve")
    parser.add_option("-t", "--msg-interval", type="eng_float", default=1.0,
                      help="inter-message interval")
    parser.add_option("-N", "--numpkts", type="eng_float", default=1,
                      help="set number of packets to transmit [default=%default]")
    parser.add_option("-s", "--size", type="eng_float", default=50,
                      help="set packet size [default=%default]")
    expert_grp = parser.add_option_group("Expert")

    transmit_path.add_options(parser, expert_grp)
    (options, args) = parser.parse_args ()

    r = gr.enable_realtime_scheduling()
    if r != gr.RT_OK:
        print "Warning: failed to enable realtime scheduling"

    # build the graph
    tb = transmit_path(options)
    tb.start()

    pkt_size = options.size
    pktno = 0
    while pktno < options.numpkts:
        pktno+=1
        print "send message %d:"%(pktno,)
        data = (pkt_size - 2) * chr(pktno & 0xff) 
        payload = struct.pack('!H', pktno & 0xffff) + data
        tb.send_pkt(payload)
        #tb.send_pkt(struct.pack('9B', 0x1, 0x80, 0x80, 0xff, 0xff, 0x10, 0x0, 0x20, 0x0))
        #this is an other example packet we could send.
        #tb.send_pkt(struct.pack('BBBBBBBBBBBBBBBBBBBBBBBBBBB', 0x1, 0x8d, 0x8d, 0xff, 0xff, 0xbd, 0x0, 0x22, 0x12, 0xbd, 0x0, 0x1, 0x0, 0xff, 0xff, 0x8e, 0xff, 0xff, 0x0, 0x3, 0x3, 0xbd, 0x0, 0x1, 0x0, 0x0, 0x0))
        time.sleep(options.msg_interval)

    tb.send_pkt(eof=True)
    tb.wait()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
