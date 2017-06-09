# Library to visualize the Mr Beam Machine States with the SK6812 LEDs
# Author: Teja Philipp (teja@mr-beam.org)
# using https://github.com/jgarff/rpi_ws281x

from __future__ import division

import signal
from neopixel import *
import time
import sys
import logging

# LED strip configuration:
# Serial numbering of LEDs on the Mr Beam modules
# order is top -> down
LEDS_RIGHT_BACK =  [0, 1, 2, 3, 4, 5, 6]
LEDS_RIGHT_FRONT = [7, 8, 9, 10, 11, 12, 13]
LEDS_LEFT_FRONT =  [32, 33, 34, 35, 36, 37, 38]
LEDS_LEFT_BACK =   [39, 40, 41, 42, 43, 44, 45]
# order is right -> left
LEDS_INSIDE =      [14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31]

# color definitions
OFF =    Color(0, 0, 0)
WHITE =  Color(255, 255, 255)
RED =    Color(255, 0, 0)
GREEN =  Color(0, 255, 0)
BLUE =   Color(0, 0, 255)
YELLOW = Color(255, 200, 0)
ORANGE = Color(226, 83, 3)



def get_default_config():
	# config file overrides these....
	return dict(
		led_count= 46,        # Number of LED pixels.
		gpio_pin= 18,         # SPI:10, PWM: 18
		led_freq_hz= 800000,  # LED signal frequency in Hz (usually 800kHz)
		led_dma= 5,           # DMA channel to use for generating signal (try 5)
		led_brigthness= 255,  # 0..255 / Dim if too much power is used.
		led_invert= False,    # True to invert the signal (when using NPN transistor level shift)

		# spread spectrum settings
		spread_spectrum_enabled= False,
		spread_spectrum_random= True,
		spread_spectrum_bandwidth= 180000,
		spread_spectrum_channel_width= 9000,
		spread_spectrum_hopping_delay_ms= 1000,

		# default frames per second
		frames_per_second= 28
	)



class LEDs():
	def __init__(self, config):
		self.config = config
		self.logger = logging.getLogger(__name__)

		print("LEDs staring up with config: %s" % self.config)
		self.logger.info("LEDs staring up with config: %s", self.config)

		# Create NeoPixel object with appropriate configuration.
		self._inti_strip(self.config['led_freq_hz'],
					self.config['spread_spectrum_enabled'],
					spread_spectrum_random=self.config['spread_spectrum_random'],
					spread_spectrum_bandwidth=self.config['spread_spectrum_bandwidth'],
					spread_spectrum_channel_width=self.config['spread_spectrum_channel_width'],
					spread_spectrum_hopping_delay_ms=self.config['spread_spectrum_hopping_delay_ms'])
		self.state = "_listening"
		self.past_states = []
		signal.signal(signal.SIGTERM, self.clean_exit)  # switch off the LEDs on exit
		self.job_progress = 0
		self.brightness = self.config['led_brigthness']
		self.fps = self.config['frames_per_second']
		self.frame_duration = self._get_frame_duration(self.fps)
		self.update_required = False
		self._last_interior = None

	def _inti_strip(self, freq_hz, spread_spectrum_enabled,
					spread_spectrum_random=False,
					spread_spectrum_bandwidth=None,
					spread_spectrum_channel_width=None,
					spread_spectrum_hopping_delay_ms=None):
		self.strip = Adafruit_NeoPixel(self.config['led_count'],
									   self.config['gpio_pin'],
									   freq_hz=freq_hz,
									   dma=self.config['led_dma'],
									   invert=self.config['led_invert'],
									   brightness=self.config['led_brigthness'])
		self.strip.set_spread_spectrum_config(
				 spread_spectrum_enabled=spread_spectrum_enabled,
				 spread_spectrum_random=spread_spectrum_random,
				 spread_spectrum_bandwidth=spread_spectrum_bandwidth,
				 spread_spectrum_channel_width=spread_spectrum_channel_width,
				 spread_spectrum_hopping_delay_ms=spread_spectrum_hopping_delay_ms)
		self.strip.begin()  # Init the LED-strip

	def change_state(self, state):
		print("state change " + str(self.state) + " => " + str(state))
		self.logger.info("state change " + str(self.state) + " => " + str(state))
		if self.state != state:
			self.past_states.append(self.state)
			while len(self.past_states) > 10:
				self.past_states.pop(0)
		self.state = state
		self.frame = 0

	def clean_exit(self, signal, msg):
		print 'shutting down, signal was: %s' % signal
		self.logger.info("shutting down, signal was: %s", signal)
		self.off()
		sys.exit(0)

	def off(self):
		for i in range(self.strip.numPixels()):
			self._set_color(i, OFF)
		self._update()

	def fade_off(self, state_length=0.5, follow_state='ClientOpened'):
		self.logger.info("fade_off()")
		old_brightness = self.brightness
		for i in range(old_brightness, -1, -1):
			self.brightness = i
			self.update_required = True
			self._update()
			time.sleep(state_length * self.frame_duration)

		for i in range(self.strip.numPixels()):
			self._set_color(i, OFF)
			self._update()

		self.brightness = old_brightness
		self.change_state(follow_state)


	# pulsing red from the center
	def error(self, frame):
		self.flash(frame, color=RED, state_length=1)

	def flash(self, frame, color=RED, state_length=2):
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)

		frames = [
			[0, 0, 0, 0, 0, 0, 0],
			[0, 0, 0, 1, 0, 0, 0],
			[0, 0, 1, 1, 1, 0, 0],
			[0, 1, 1, 1, 1, 1, 0],
			[1, 1, 1, 1, 1, 1, 1],
			[1, 1, 1, 1, 1, 1, 1],
			[0, 1, 1, 1, 1, 1, 0],
			[0, 0, 1, 1, 1, 0, 0],
			[0, 0, 0, 1, 0, 0, 0]
		]

	 	f = int(round(frame / state_length)) % len(frames)

		for r in involved_registers:
			for i in range(l):
				if frames[f][i] >= 1:
					self._set_color(r[i], color)
				else:
					self._set_color(r[i], OFF)
		self._update()

	def listening(self, frame, state_length=2):
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)

		f_count = state_length * self.fps
		dim = abs((frame/state_length % f_count*2) - (f_count-1))/f_count

		color = self.dim_color(ORANGE, dim)
		for r in involved_registers:
			for i in range(l):
				if i == l-1:
					self._set_color(r[i], color)
				else:
					self._set_color(r[i], OFF)

		self._update()

	def all_on(self):
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]

		color = WHITE
		for r in involved_registers:
			l = len(r)
			for i in range(l):
				self._set_color(r[i], color)
		self.brightness = 255
		self._update()

	# alternating upper and lower yellow
	def upload(self, frame, state_length=8):
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)
		fwd_bwd_range = range(l) + range(l-1, -1, -1)

		frames = [
			[1, 1, 1, 0, 0, 0, 0],
			[0, 0, 0, 0, 1, 1, 1]
		]

		f = int(round(frame / state_length)) % len(frames)

		for r in involved_registers:
			for i in range(l):
				if frames[f][i] >= 1:
					self._set_color(r[i], YELLOW)
				else:
					self._set_color(r[i], OFF)

		self._update()

	def progress(self, value, frame, color_done=WHITE, color_drip=BLUE, state_length=2):
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)
		c = int(round(frame / state_length)) % l

		# self.illuminate() # interior light always on

		for r in involved_registers:
			for i in range(l):

				bottom_up_idx = l-i-1
				threshold = int(value) / 100.0 * (l-1)
				if threshold < bottom_up_idx:
					if i == c:
						self._set_color(r[i], color_drip)
					else:
						self._set_color(r[i], OFF)

				else:
					self._set_color(r[i], color_done)


		self._update()

	# pauses the progress animation with a pulsing drip
	def progress_pause(self, value, frame, breathing=True, color_done=WHITE, color_drip=BLUE, state_length=1.5):
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)
		f_count = state_length * self.fps
		dim = abs((frame/state_length % f_count*2) - (f_count-1))/f_count if breathing else 1
		# self.illuminate() # interior light always on

		for r in involved_registers:
			for i in range(l):
				bottom_up_idx = l-i-1
				threshold = value / 100.0 * (l-1)
				if threshold < bottom_up_idx:
					if i == bottom_up_idx / 2:
						color = self.dim_color(color_drip, dim)
						self._set_color(r[i], color)
					else:
						self._set_color(r[i], OFF)

				else:
					self._set_color(r[i], color_done)


		self._update()

	# def drip(self, frame, color=BLUE, state_length=2):
	# 	involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
	# 	l = len(LEDS_RIGHT_BACK)
	# 	c = int(round(frame / state_length)) % l
    #
	# 	for r in involved_registers:
	# 		for i in range(l):
	# 			if i == c:
	# 				self._set_color(r[i], color)
	# 			else:
	# 				self._set_color(r[i], OFF)
    #
	# 	self._update()

	def idle(self, frame, color=WHITE, state_length=1):
		leds = LEDS_RIGHT_BACK + list(reversed(LEDS_RIGHT_FRONT)) + LEDS_LEFT_FRONT + list(reversed(LEDS_LEFT_BACK))
		c = int(round(frame / state_length)) % len(leds)
		for i in range(len(leds)):
			if i == c:
				self._set_color(leds[i], color)
			else:
				self._set_color(leds[i], OFF)


		self._update()

	def job_finished(self, frame, state_length=1):
		# self.illuminate()  # interior light always on
		involved_registers = [LEDS_RIGHT_FRONT, LEDS_LEFT_FRONT, LEDS_RIGHT_BACK, LEDS_LEFT_BACK]
		l = len(LEDS_RIGHT_BACK)
		f = int(round(frame / state_length)) % (self.fps + l*2)

		if f < l*2:
			for i in range(int(round(f/2))-1, -1, -1):
				for r in involved_registers:
					self._set_color(r[i], GREEN)

		else:
			for i in range(l-1, -1, -1):
				for r in involved_registers:
					brightness = 1 - (f - 2*l)/self.fps * 1.0
					col = self.dim_color(GREEN, brightness)
					self._set_color(r[i], col)

		self._update()

	def shutdown(self, frame):
		self.static_color(RED)

	def shutdown_prepare(self, frame, duration_seconds=5):
		brightness_start_val = 205
		peak_frame = duration_seconds * self.fps
		on = frame % 10 > 3
		brightness = None
		if on:
			if (frame <= peak_frame):
				brightness = int(brightness_start_val - (brightness_start_val/peak_frame) * frame)
				brightness = brightness if brightness > 0 else 0
				myColor = self.dim_color(RED, brightness)
			else:
				myColor = RED
		else:
			myColor = OFF
		self.static_color(myColor)

	def set_interior(self, color):
		if self._last_interior != color:
			self._last_interior = color
			leds = LEDS_INSIDE
			l = len(leds)
			for i in range(l):
				self._set_color(leds[i], color)

			self._update()

	def static_color(self, color=WHITE):
		leds = LEDS_RIGHT_FRONT + LEDS_LEFT_FRONT + LEDS_RIGHT_BACK + LEDS_LEFT_BACK
		for i in range(len(leds)):
			self._set_color(leds[i], color)
		self._update()

	def dim_color(self, col, brightness):
		r = (col & 0xFF0000) >> 16
		g = (col & 0x00FF00) >> 8
		b = (col & 0x0000FF)
		return Color(int(r*brightness), int(g*brightness), int(b*brightness))

	def demo_state(self, frame):
		f = frame % 4300
		if f < 1000:
			return "idle"
		elif f < 2000:
			return "progress:" + str((f-1000)/20)
		elif f < 2200:
			return "pause:50"
		elif f < 3200:
			return "progress:" + str((f-1200)/20)
		elif f < 4000:
			return "job_finished"
		else:
			return "warning"

	def set_fps(self, fps):
		fps = int(fps)
		if fps < 1: fps = 1
		self.fps = fps
		self.frame_duration = self._get_frame_duration(fps)
		self.logger.info("set_fps() Changed animation speed: fps:%d (%s s/frame)" % (self.fps, self.frame_duration))

	def spread_spectrum(self, params):
		self.logger.info("spread_spectrum()")
		enabled = params.pop(0)
		if enabled == 'off':
			self._inti_strip(LED_FREQ_HZ, False)
			self.logger.info("spread_spectrum() off, led frequency is: %s", LED_FREQ_HZ)
		elif enabled == 'on' and len(params) in (4,5):
			try:
				freq = int(params.pop(0))
				bandwidth = int(params.pop(0))
				channel_width = int(params.pop(0))
				hopping_delay = int(params.pop(0))
				random = params.pop(0).startswith('r') if len(params) > 0 else False
				self.logger.info("spread_spectrum() on: freq=%s, bandwidth=%s, channel_width=%s, hopping_delay=%s, random:%s", freq, bandwidth, channel_width, hopping_delay, random)
				self._inti_strip(freq, True,
					spread_spectrum_random=random,
					spread_spectrum_bandwidth=bandwidth,
					spread_spectrum_channel_width=channel_width,
					spread_spectrum_hopping_delay_ms=hopping_delay)
			except:
				self.logger.exception("spread_spectrum() Exception while executing command %s", self.state)
		else:
			self.logger.info("spread_spectrum() invalid command or params. Usage: spread_spectrum:<on|off>:<center_frequency>:<bandwidth>:<channel_width>:<hopping_delay> eg: 'spread_spectrum:on:800000:180000:9000:1'")

	def rollback(self, steps=1):
		self._last_interior = None
		if len(self.past_states) >= steps:
			for x in range(0, steps):
				old_state = self.past_states.pop()
				self.logger.info("Rolleback step %s/%s: rolling back from '%s' to '%s'", x, steps, self.state, old_state)
				self.state = old_state
		else:
			self.logger.warn("Rolleback: Can't rollback %s steps, max steps: %s", steps, len(self.past_states))
			if len(self.past_states) >= 1:
				self.state = self.past_states.pop()
			else:
				self.state = "_listening"
			self.logger.warn("Rolleback: fallback to %s", self.state)

	def loop(self):
		try:
			self.frame = 0
			while True:
				data = self.state
				if not data:
					state_string = "off"  # self.demo_state(self.frame)
				else:
					state_string = data

				# split params from state string
				params = state_string.split(':')
				state = params.pop(0)

				# default interior color
				interior = WHITE

				# Daemon listening
				if state == "_listening":
					self.listening(self.frame)

				# test purposes
				elif state == "all_on":
					self.all_on()

				elif state == "rollback":
					self.rollback(2)

				# Server
				elif state == "Startup":
					self.listening(self.frame)
					# self.idle(self.frame, color=Color(20, 20, 20), fps=10)
				elif state == "ClientOpened":
					self.idle(self.frame)
				elif state == "ClientClosed":
					self.listening(self.frame)
					# self.idle(self.frame, color=Color(20, 20, 20), fps=10)

				# Machine
				# elif state == "Connected":
				# 	self.idle(self.frame)
				# elif state == "Disconnected":
				# 	self.idle(self.frame, fps=10)
				elif state == "Error":
					self.error(self.frame)
				elif state == "ShutdownPrepare":
					self.shutdown_prepare(self.frame)
				elif state == "Shutdown":
					self.shutdown(self.frame)
				elif state == "ShutdownPrepareCancel":
					self.rollback(2)

				# File Handling
				elif state == "Upload":
					self.upload(self.frame)

				# Laser Job
				elif state == "PrintStarted":
					self.progress(0, self.frame)
				elif state == "PrintDone":
					self.job_progress = 0
					self.job_finished(self.frame)
				elif state == "PrintCancelled":
					self.job_progress = 0
					self.fade_off()
				elif state == "PrintPaused":
					self.progress_pause(self.job_progress, self.frame)
				elif state == "PrintPausedTimeout":
					self.progress_pause(self.job_progress, self.frame, False)
				elif state == "PrintPausedTimeoutBlock":
					if self.frame > self.fps:
						self.change_state("PrintPausedTimeout")
					else:
						self.progress_pause(self.job_progress, self.frame, False, color_drip=RED)
				elif state == "PrintResumed":
					self.progress(self.job_progress, self.frame)
				elif state == "progress":
					self.job_progress = params.pop(0)
					self.progress(self.job_progress, self.frame)
				elif state == "job_finished":
					self.job_finished(self.frame)
				elif state == "pause":
					self.progress_pause(params.pop(0), self.frame)
				elif state == "ReadyToPrint":
					self.flash(self.frame, color=BLUE, state_length=2)
				elif state == "ReadyToPrintCancel":
					self.idle(self.frame)

				# Slicing
				elif state == "SlicingStarted":
			 		self.progress(params.pop(0), self.frame, color_done=BLUE, color_drip=WHITE, state_length=3)
				elif state == "SlicingDone":
					self.progress(params.pop(0), self.frame, color_done=BLUE, color_drip=WHITE, state_length=3)
				elif state == "SlicingCancelled":
					self.idle(self.frame)
				elif state == "SlicingFailed":
					self.fade_off()
				elif state == "SlicingProgress":
					self.progress(params.pop(0), self.frame, color_done=BLUE, color_drip=WHITE, state_length=3)

				# Settings
				elif state == "SettingsUpdated":
					if self.frame > 50:
						self.rollback()
					else:
						self.flash(self.frame, color=WHITE, state_length=1)

				# other
				elif state == "off":
					self.off()
					interior = OFF
				elif state == "brightness":
					bright = params.pop(0)
					if bright > 255:
						bright = 255
					elif bright < 0:
						bright = 0
					self.brightness = bright
					self.update_required = True
				elif state == "all_red":
					self.static_color(RED)
				elif state == "all_green":
					self.static_color(GREEN)
				elif state == "all_blue":
					self.static_color(BLUE)
				elif state == "fps":
					self.set_fps(params.pop(0))
					self.rollback()
				elif state == "spread_spectrum":
					self.spread_spectrum(params)
					self.rollback()
				else:
					self.idle(self.frame, color=Color(20, 20, 20), state_length=2)

				# set interior at the end
				self.set_interior(interior)

				self.frame += 1
				time.sleep(self.frame_duration)

		except KeyboardInterrupt:
			self.logger.exception("KeyboardInterrupt Exception in animation loop:")
			self.clean_exit(signal.SIGTERM, None)
		except:
			self.logger.exception("Some Exception in animation loop:")
			print("Some Exception in animation loop:")
			
	def _set_color(self, i, color):
		c = self.strip.getPixelColor(i)
		if(c != color):
			self.strip.setPixelColor(i, color)
			self.update_required = True
			# self.logger.info("colors did not match update %i : %i" % (color,c))
		else:
			# self.logger.debug("skipped color update of led %i" % i)
			pass
			
	def _update(self):
		if(self.update_required):
			self.strip.setBrightness(self.brightness)
			self.strip.show();
			self.update_required = False
			# self.logger.info("state: %s |    flush  !!!", self.state)
		else:
			# self.logger.info("state: %s | no flush   - ", self.state)
			pass

	def _get_frame_duration(self, fps):
		return (1.0 / int(fps)) if int(fps)>0 else 1.0
			