import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import serial
import struct
import matplotlib
import threading
import time
import argparse

class RFExplorer(object):

	def __init__(self, port):
		self.serial_interface = serial.Serial(port, 500000, timeout=1)
		self.recieve_running = False
		self.frames = []
		#np.zeros(112)

	def request_config(self):
		#This is really more like request version. You only get the current config back if you use set_sweep
		message = struct.pack('cBcc', '#', 4, 'C', '0')
		self.serial_interface.write(message)

	def set_sweep(self, start_freq, end_freq, amplitude_max, amplitude_min):
		message = struct.pack('cB', '#', 32)
		message += 'C2-F:{0:07d},{1:07d},{2:03d},{3:03d}\r\n'.format(start_freq, end_freq, amplitude_max, amplitude_min)
		self.serial_interface.write(message)
		
	def read_data(self):
		buffer = ""
		while True:
			buffer = buffer + self.serial_interface.read()
			if buffer[len(buffer)-2:] == '\r\n':
				break
		if len(buffer) > 2:
			#Break off the \r\n
			#Why not strip? The buffer contains binary data, strip might remove things we want
			return buffer[:-2]
		return buffer

	def process_data(self, data):
		if data[0] == '$':
			if data[1] == 'S':
				#Specturm data
				#The math in this list comprehension converts the input values to dBm
				#RFExplorer docs indicate this should be consistent for all rf modules
				self.frames.append(np.array([(-1.0*float(ord(x)))/2.0 for x in data[3:]]))
		elif data[0] == '#':
			if data[1:5] == 'C2-F':
				config_data = data[7:]
				config_array = config_data.split(',')
				self.start_freq = int(config_array[0])
				self.freq_step = int(config_array[1])
				self.amplitude_max = int(config_array[2])
				self.amplitude_min = int(config_array[3])
				self.sweep_steps = int(config_array[4])
				self.min_freq = int(config_array[7])
				self.max_freq = int(config_array[8])
				self.max_span = int(config_array[9])
				self.rbw = int(config_array[10])
		else:
			print("Unknown Data: %s" % data)

	def _recieve(self):
		while self.recieve_running:
			self.process_data(self.read_data())

	def start_recieve_thread(self):
		self.recieve_running = True
		self.recieve_thread = threading.Thread(target=self._recieve)
		self.recieve_thread.start()
		return self.recieve_thread

	def stop_recieve_thread(self):
		self.recieve_running = False

	def close(self):
		self.recieve_running = False
		self.serial_interface.close()

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Python interface to the RFExplorer')
	parser.add_argument('-c', '--capture', help='Data capture mode', action='store_const', const=True)
	parser.add_argument('-d', '--device', help='Serial device RFExplorer presents as')
	parser.add_argument('-n', '--samples', help='Number of samples to capture per step', default=32)
	parser.add_argument('-o', '--output', help='File to output captured samples to. (File is in Numpy npy format)', default='samples.npy')
	parser.add_argument('-b', '--sweepbegin', help='Frequency to begin sweeep from in KHz', default=240000)
	parser.add_argument('-e', '--sweepend', help='Frequency to end sweep at in KHz', default=250000)
	parser.add_argument('-p', '--plot', help='Plot captured data', action='store_const', const=True)
	parser.add_argument('-i', '--input', help='Input file for plot', default='samples.npy')
	parser.add_argument('-z', '--baseline', help='Baseline data to subtract from collected data', default=False)

	args = parser.parse_args()

	if args.capture:
		exp_interface = RFExplorer(args.device)
		exp_interface.start_recieve_thread()
		exp_interface.set_sweep(int(args.sweepbegin), int(args.sweepend), -51, -120)

		while len(exp_interface.frames) < int(args.samples):
			print len(exp_interface.frames)
	
		exp_interface.stop_recieve_thread()
		output_array = np.vstack(exp_interface.frames)
		with open(args.output, 'w') as output_file:
			np.save(output_file, output_array)
		time.sleep(1)
		exp_interface.close()
	elif args.plot:
		with open(args.input, 'r') as input_file:
			data = np.load(input_file)
			if(args.baseline):
				with open(args.baseline, 'r') as baseline_file:
					baseline_data = np.average(np.load(baseline_file), axis=0)
					data = np.subtract(data, baseline_data)
			plot = matplotlib.pyplot.pcolormesh(data)
			matplotlib.pyplot.show()
			
