#!/usr/bin/env python

#
# @author: youlizhao.nju@gmail.com
#
# Decoder of IEEE 802.15.4 RADIO Packets using WiFi Setup
#   * WiFi channel 6 Rx: 20M (wifi_zigbee.py)
#   * ZigBee chan 17 Tx: 2M  (cc2420_txtest_uhd.py) 
#
from gnuradio import gr, eng_notation, uhd
from gnuradio import ucla
from gnuradio import blks2
from gnuradio.ucla_blks import ieee802_15_4_pkt
from gnuradio.eng_option import eng_option
from optparse import OptionParser
import math, struct, time, sys

class stats(object):
    def __init__(self):
        self.npkts = 0
        self.nright = 0

class oqpsk_rx_graph (gr.top_block):
    def __init__(self, options, rx_callback):
        gr.top_block.__init__(self)

        u = uhd.usrp_source(device_addr="addr0=192.168.20.4",stream_args=uhd.stream_args(cpu_format="fc32", channels=range(1)))

        self.usrp_decim = 5
        self.sampling_rate = 100e6 / self.usrp_decim
        u.set_samp_rate(self.sampling_rate)
        
        # WiFi Channel 6
        self.usrp_freq = 2.437e9
        u.set_center_freq(self.usrp_freq)

        options.gain = 20
        u.set_gain(options.gain)

        u.set_subdev_spec("A:0", 0)
        u.set_antenna("TX/RX", 0)

        self.samples_per_symbol = 2
        self.filter_decim = 5
        self.data_rate = int (self.sampling_rate
                              / self.samples_per_symbol
                              / self.filter_decim)

        print "data_rate = ", eng_notation.num_to_str(self.data_rate)
        print "samples_per_symbol = ", self.samples_per_symbol
        print "usrp_decim = ", self.usrp_decim
        print "usrp2_gain = ", options.gain

        # ZigBee Channel 17
        self.chan1_freq = ieee802_15_4_pkt.chan_802_15_4.chan_map[options.channel1]
        self.chan1_num = options.channel1
        self.chan1_offset = self.usrp_freq - self.chan1_freq

        print "Centering USRP2 at = ", self.usrp_freq
        print "Channel ", self.chan1_num, " freq = ", self.usrp_freq - self.chan1_offset


        # Creating a filter for channel selection
        chan_coeffs = gr.firdes.low_pass(   1.0, # filter gain
                self.sampling_rate,              # sampling rate
                2e6,                           # cutoff frequency  
                2e6,                           # bandwidth
                gr.firdes.WIN_HANN)              # filter type           

        #print "Length of chan_coeffs = ", len(chan_coeffs)
        #print chan_coeffs

        # Decimating channel filters 
        self.ddc1 = gr.freq_xlating_fir_filter_ccf(
                     self.filter_decim,  # decimation rate
                     chan_coeffs,        # taps
                     self.chan1_offset,  # frequency translation amount  
                     self.sampling_rate) # input sampling rate   
 

        self.packet_receiver1 = ieee802_15_4_pkt.ieee802_15_4_demod_pkts(
            self,
            callback=rx_callback,
            sps=self.samples_per_symbol,
            channel=self.chan1_num,
            threshold=-1,
            log=options.log)

        self.u = u
        self.squelch = gr.pwr_squelch_cc(options.squelch, gate=True)

        self.connect(self.u,self.squelch)
        self.connect(self.squelch, self.ddc1, self.packet_receiver1)
        self.connect(self.ddc1, gr.file_sink(gr.sizeof_gr_complex, 'wifi-zigbee-ddc.dat'))


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

    def rx_callback_pcap(ok, payload, chan_num):
        # Output this packet in pcap format
        pcap_capture_time = time.time()
        pcap_capture_msec = math.modf(pcap_capture_time)[0] * 1e6
        pcap_pkt_header = struct.pack('IIIIB',
                                      pcap_capture_time,
                                      pcap_capture_msec,
                                      len(payload)+1,
                                      len(payload)+1,
                                      chan_num)
        fout.write(pcap_pkt_header)
        fout.write(payload)
        fout.flush()

    parser = OptionParser (option_class=eng_option)
    parser.add_option ("-c", "--channel1", type="int", default=17,
            help="First channel to capture on", metavar="FREQ")
    parser.add_option ("-f", "--filename", type="string",
            default="rx.dat", help="write data to FILENAME")
    parser.add_option ("-g", "--gain", type="eng_float", default=40,
            help="set Rx gain in dB [0,70]")
    parser.add_option ("-s", "--squelch", type="eng_float", default=-40.0,
            help="Set Squelch filter level")
    parser.add_option("", "--log", action="store_true", default=False,
            help="Log all parts of flow graph to files (CAUTION: lots of data)")


    (options, args) = parser.parse_args ()

    st1 = stats()
    st2 = stats()

    # Setup the libpcap output file
    fout = open(options.filename, "w")
    # Write the libpcap Global Header
    pcap_glob_head = struct.pack('IHHiIII',
            0xa1b2c3d4,    # Magic Number
            2,             # Major Version Number
            4,             # Minor Version Number
            0,
            0,
            65535,
            221)           # Link Layer Type = 802.15.4 PHY Channel
    fout.write(pcap_glob_head)

    r = gr.enable_realtime_scheduling()
    if r == gr.RT_OK:
        print "Enabled Realtime"
    else:
        print "Failed to enable Realtime. Did you run as root?"

    tb = oqpsk_rx_graph(options, rx_callback_pkt)   

    tb.start()

    tb.wait()

if __name__ == '__main__':
    # insert this in your test code...
    #import os
    #print 'Blocked waiting for GDB attach (pid = %d)' % (os.getpid(),)
    #raw_input ('Press Enter to continue: ')

    main()
