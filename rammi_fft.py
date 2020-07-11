import numpy as np
import scipy.interpolate
import math
import time

class RammiFFT (object):

    """
    RammiFFT receives (preferably normalized) PCM audio data and calculates a Fast Fourier Transform on that data.
    Several steps are taken after to adjust the FFT to more closely match human hearing and beautify the data.

    Typical usage:

        ram_ft = RammiFFT()
        ram_ft.intake_samples(collection)
        ram_ft.full_transform()
        somehow_display(ram_ft.frequency_spectrum_final)

    RammiFFT exposes the following buffers which contain the interesting data that you came for:

        * self.time_domain_buffer
        * self.windowed_time_domain_buffer
        * self.frequency_spectrum_raw               1st pass
        * self.frequency_spectrum_avg               2nd pass
        * self.frequency_spectrum_loudness_adj      3rd pass        Order cannot be changed without rewriting code
        * self.frequency_spectrum_trimmed           4th pass
        * self.frequency_spectrum_interpolated      5th pass
        * self.frequency_spectrum_final             same as 5th pass, named for convenience

    Other useful data:
        
        * self.time_domain_buffer_size
        * self.frequency_spectrum_size_raw
        * self.frequency_spectrum_size_avg
        * self.frequency_spectrum_size_loudness_adj
        * self.frequency_spectrum_size_trimmed
        * self.frequency_spectrum_size_interpolated
        * self.logarithmic_transformation_curve

        * self.sample_rate
        * self.nyquist
    """

    def __init__(self, sr=44100, buf_size=1024, avg_per_oct=4, ref_ratio=1/3, trim_ratio = 9/10, beautified_size=256):

            ## Vanilla Fourier Transform

        self.sample_rate = sr                # Hz; rate of samples taken from signal per second
        self.nyquist = self.sample_rate / 2

        if math.log(buf_size, 2) % 1 != 0:
            raise ValueError('RammiFFT.__init__: buf_size ' + str(buf_size) + ' is not a power of 2')

        self.time_domain_buffer_size = buf_size # Number of samples that will be held and analyzed at once (power of 2)
                                                    # This does not mean we need this many new samples every frame;
                                                    # We will replace the oldest X samples with the newest X at the front;
                                                    # This number is directly responsible for the frequency resolution of the output
                                                    # as well as the length of time the FFT calculation takes
        time_step = 1 / self.sample_rate
        #self.time_axis = np.arange(0, self.time_domain_buffer_size * time_step, time_step)      # Just the time value (x) of samples

        self.time_domain_buffer = np.array([0 for i in range(self.time_domain_buffer_size)], dtype='float32')   # Raw samples to be processed are stored here
                                                                                                                # (INPUT)
        self.windowed_time_domain_buffer = np.array([0 for i in range(self.time_domain_buffer_size)], dtype='float32')

        # rfft specifies real input only; fft uses complex input
        self.frequency_axis_raw = (np.fft.rfftfreq(self.time_domain_buffer_size) * self.sample_rate)[1:]
                            # Like time_axis but for frequency bands in the finished (unaveraged) spectrum
                            # We cut off the 0 band because it isn't useful and to keep the length of
                            # the frequency spectrum to a power of 2

        self.frequency_spectrum_size_raw = len(self.frequency_axis_raw)
        self.bandwidth_raw = (2 / self.time_domain_buffer_size) * self.nyquist
        self.frequency_bandwidth_raw = self.frequency_axis_raw[1] - self.frequency_axis_raw[0]  # Bandwidth of unaveraged frequency bands

        self.frequency_spectrum_raw = np.array([0 for i in range(self.frequency_spectrum_size_raw)], dtype='float32')   # Unaveraged frequency power values are stored here
                                                                                                                        # (1st PASS)

            ## Logarithmic Averaging

        # Determine how many octaves are possible in the spectrum, given that an octave shift is twice/half of a given frequency, the maximum frequency
        # is the Nyquist frequency, and we are limited by the bandwidth of each frequency band

        self.octaves_in_spectrum = 1
        nyq = self.nyquist / 2
        while nyq > self.bandwidth_raw:     # We could specify a different 'minimum bandwidth,' but I don't know why any other value would be desirable
            self.octaves_in_spectrum += 1
            nyq /= 2

        self.averages_per_octave = avg_per_oct   # WE ARE FREE TO SET THIS VALUE DIRECTLY, DOES NOT IMPACT ANY OTHER PART OF THE MATH

        self.frequency_spectrum_size_avg = self.octaves_in_spectrum * self.averages_per_octave
        self.frequency_spectrum_avg = np.array([0 for i in range(self.frequency_spectrum_size_avg)], dtype='float32')
                                    # Logarithmically spaced frequency power value averages are stored here
                                    # (2nd PASS)

            ## Loudness Adjustment

        reference_point_as_ratio = ref_ratio    # We are preparing to scale frequency_spectrum_avg by a logarithmic function, and this number represents the frequency band
                                                # that we want to leave unchanged (log ... = 1.0) as a fraction of the whole buffer size

        reference_index = int(round(self.frequency_spectrum_size_avg * reference_point_as_ratio)) - 1

        # We add 1 to both values in math.log because we want to shave off all negative values while keeping the reference point the same
        # Look at a graph of y = log(x, b) for further reference

        self.logarithmic_transformation_curve = np.array([math.log(i + 1, reference_index + 1) for i in range(len(self.frequency_spectrum_avg))])

        self.frequency_spectrum_size_loudness_adj = self.frequency_spectrum_size_avg
        self.frequency_spectrum_loudness_adj = np.array(self.frequency_spectrum_avg, dtype='float32')       # Loudness adjusted version of averaged spectrum
                                                                                                            # (3rd PASS)

            ## Trimming

        trim_point_as_ratio = trim_ratio
        self.trim_index = int(round(self.frequency_spectrum_size_loudness_adj * trim_point_as_ratio)) # deliberately not subtracting 1 from trim_index

        self.frequency_spectrum_trimmed = self.frequency_spectrum_loudness_adj[:self.trim_index]
        self.frequency_spectrum_trimmed[-1] = 0
                                                        # Trimmed version of loudness adjusted spectrum, because high end
                                                        # of spectrum includes very little useful data and takes up space
                                                        # (4th PASS)
        self.frequency_spectrum_size_trimmed = len(self.frequency_spectrum_trimmed)

            ## Spline Interpolation

        self.frequency_spectrum_size_interpolated = beautified_size                             # Trimmed spectrum filled in with interpolated values to raise resolution
                                                                                                # (5th PASS)
        self.frequency_spectrum_interpolated = np.array([0 for i in range(beautified_size)])
        self.frequency_spectrum_final = self.frequency_spectrum_interpolated                    # Same data with a more convenient name for end use

    def spectrum_index_from_frequency(self, freq):

        if freq < self.bandwidth_raw:
            return 0
        elif freq > self.nyquist - self.bandwidth_raw / 2:
            return self.frequency_spectrum_size_raw - 1

        fraction = freq / self.sample_rate  # This renormalizes the frequency back to a value between 0 and 1
        return int(round(fraction * self.time_domain_buffer_size))

    def intake_samples(self, intake):
        
        start_time = time.time()

        number_of_samples = len(intake)

        if number_of_samples >= self.time_domain_buffer_size:
            self.time_domain_buffer = np.array(intake[(number_of_samples - self.time_domain_buffer_size) : ])
        else:

            # Shift all existing samples by number_of_samples, discarding the last [number_of_samples] samples
            for i in range(self.time_domain_buffer_size - number_of_samples - 1, -1, -1):
                #print('replacing time_domain_buffer[' + str(i + number_of_samples) + '] with value of [' + str(i) + '] = ' + str(self.time_domain_buffer[i]))
                self.time_domain_buffer[i + number_of_samples] = self.time_domain_buffer[i]

            # Replace the unaltered portion of the array with the new samples
            for i in range(number_of_samples):
                #print('replacing time_domain_buffer[' + str(i) + '] with new value ' + str(intake[i]))
                self.time_domain_buffer[i] = intake[i]
                #print('verifying time_domain_buffer[' + str(i) + '] = ' + str(self.time_domain_buffer[i]))

        #print('intake_samples: ' + str(time.time() - start_time) + ', len(intake): ' + str(number_of_samples))

    def apply_window(self):

        start_time = time.time()

        def hamming_window(buff):

            hamm = np.array([0.5 - 0.46 * np.cos(2 * np.pi * i / (self.time_domain_buffer_size - 1))
                             for i in range(self.time_domain_buffer_size)])

            return buff * hamm

        self.windowed_time_domain_buffer = hamming_window(self.time_domain_buffer)
        
        #print('apply_window ' + str(time.time() - start_time))

    def transform_raw(self):

        start_time = time.time()

        self.apply_window()
        self.frequency_spectrum_raw = abs(np.fft.rfft(self.windowed_time_domain_buffer).real / (self.time_domain_buffer_size / 32))[1:]
       # for band in self.frequency_spectrum_raw:
       #     if abs(band) >= 1:
       #         print('transform_raw: VALUE ' + str(abs(band)) + ' IS GREATER THAN 1')

        #print('transform_raw: ' + str(time.time() - start_time))

    def transform_avg(self):

        start_time = time.time()

        for i in range(self.octaves_in_spectrum):

            low_freq = 0 if i == 0 else self.nyquist / (2 ** (self.octaves_in_spectrum - i))    # These are the endpoints of whole octaves
            high_freq = self.nyquist / (2 ** (self.octaves_in_spectrum - i - 1))
            freq_step = (high_freq - low_freq) / self.averages_per_octave                         # This is the increment between those endpoints

            f = low_freq
            for j in range(self.averages_per_octave):

                # Actual averaging happens here
                
                low_index = self.spectrum_index_from_frequency(f)
                high_index  = self.spectrum_index_from_frequency(f + freq_step)
                average = 0

                for k in range(low_index, high_index + 1):
                    average += self.frequency_spectrum_raw[k]

                average /= high_index - low_index + 1

                offset = j + i * self.averages_per_octave
                self.frequency_spectrum_avg[offset] = average

                f += freq_step

        #print('transform_avg: ' + str(time.time() - start_time))

    def loudness_adjust(self):
        """ Compensate for human hearing by applying a logarithmic curve to reduce lower frequencies and amplify higher ones
            Because this is for personal use and not advertised as a multipurpose toolset, this only affects frequency_spectrum_avg """

        self.frequency_spectrum_loudness_adj = self.frequency_spectrum_avg * self.logarithmic_transformation_curve

    def trim(self):

        self.frequency_spectrum_trimmed = self.frequency_spectrum_loudness_adj[:self.trim_index]
        self.frequency_spectrum_trimmed[-1] = 0

    def interpolate(self):

        x_old = list(range(self.frequency_spectrum_size_trimmed))  # The original X axis of the frequency spectrum
                                                                        # We don't care about the actual frequency ranges for this purpose,
                                                                        # so we're just treating the array indices as the X axis

        spline = scipy.interpolate.UnivariateSpline(x_old, self.frequency_spectrum_trimmed)
        spline.set_smoothing_factor(0)

        x_new = np.linspace(0, self.frequency_spectrum_size_trimmed - 1, self.frequency_spectrum_size_interpolated)

        self.frequency_spectrum_interpolated = spline(x_new)
        print(self.frequency_spectrum_interpolated)
        self.frequency_spectrum_final = self.frequency_spectrum_interpolated

    def full_transform(self):

        self.transform_raw()
        self.transform_avg()
        self.loudness_adjust()
        self.trim()
        self.interpolate()
