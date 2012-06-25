#!/usr/bin/env python

#
# Decoder of IEEE 802.15.4 RADIO Packets.
#
# Modified by: Thomas Schmid, Leslie Choong, Mikhail Tadjikov
#
  
from gnuradio import gr, eng_notation
from gnuradio.ucla_blks import ieee802_15_4_pkt
from gnuradio.eng_option import eng_option
from optparse import OptionParser
import struct, sys, time, math

from uhd_interface import uhd_receiver       
    
class oqpsk_rx_graph (gr.top_block):
    def __init__(self, options, rx_callback):
        gr.top_block.__init__(self)

        if (options.rx_freq) is not None or (options.channel is not None):
            if options.channel is not None:
              self.chan_num = options.channel
              options.rx_freq = ieee802_15_4_pkt.chan_802_15_4.chan_map[self.chan_num]

            u = uhd_receiver(options.rx_args,
                             options.bandwidth,
                             options.rx_freq, options.rx_gain,
                             options.spec, options.antenna,
                             options.verbose, options.external)
        elif options.infile is not None:
            u = gr.file_source(gr.sizeof_gr_complex, options.infile)
        else:
            sys.stderr.write("--freq or --infile must be specified\n")
            raise SystemExit

        self.samples_per_symbol = 2
        self.data_rate = options.bandwidth / self.samples_per_symbol

        self.packet_receiver = ieee802_15_4_pkt.ieee802_15_4_demod_pkts(self,
                                callback=rx_callback,
                                sps=self.samples_per_symbol,
                                symbol_rate=self.data_rate,
                                channel=self.chan_num,
                                threshold=options.threshold)

        self.src = u
        #self.squelch = gr.pwr_squelch_cc(-65, gate=True)
        self.connect(self.src,
         #       self.squelch,
                self.packet_receiver)

    def add_options(normal, expert):
        """
        Adds usrp-specific options to the Options Parser
        """
        normal.add_option("", "--infile", type="string",
                          help="select input file to TX from")
        normal.add_option ("-c", "--channel", type="eng_float", default=15,
                          help="Set 802.15.4 Channel to listen on channel %default", metavar="FREQ")
        normal.add_option("-v", "--verbose", action="store_true", default=False)
        normal.add_option("-W", "--bandwidth", type="eng_float",
                          default=4000e3,
                          help="set symbol bandwidth [default=%default]")
        normal.add_option ("-t", "--threshold", type="int", default=-1)
        expert.add_option("", "--log", action="store_true", default=False,
                          help="Log all parts of flow graph to files (CAUTION: lots of data)")
        uhd_receiver.add_options(normal)

    # Make a static method to call before instantiation
    add_options = staticmethod(add_options)

def main ():
    global n_rcvd, n_right

    n_rcvd = 0
    n_right = 0

    def rx_callback_pkt(ok, payload, chan_num):
        global n_rcvd, n_right
        n_rcvd += 1
        if ok:
            n_right += 1

        (pktno,) = struct.unpack('!H', payload[0:2])
        print "ok = %5r  pktno = %4d  len(payload) = %4d  %d/%d" % (ok, pktno, len(payload),
                                                                    n_rcvd, n_right)
        print "  payload: " + str(map(hex, map(ord, payload)))
        print " ------------------------"
        sys.stdout.flush()

        
    parser = OptionParser (option_class=eng_option, conflict_handler="resolve")
    expert_grp = parser.add_option_group("Expert")
    oqpsk_rx_graph.add_options(parser, expert_grp)
    (options, args) = parser.parse_args ()

    r= gr.enable_realtime_scheduling()
    if r == gr.RT_OK:
        print "Enabled Realtime"
    else:
        print "Failed to enable Realtime"

    tb = oqpsk_rx_graph(options, rx_callback_pkt)
    tb.start()

    tb.wait()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
