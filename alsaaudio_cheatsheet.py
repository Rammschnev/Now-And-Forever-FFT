from alsaaudio import *
from time import sleep

## This program demonstrates a simplest case example of how to record PC audio playback as PCM data and then
## play that audio again manually through code.

## The intended purpose for this information at the time of writing is to record PCM audio from a bluetooth connected
## android phone, which is shockingly simple and plug-and-play.

recording_pcm = PCM(type=PCM_CAPTURE, mode=PCM_NONBLOCK, device='pulse')
playback_pcm = PCM(type=PCM_PLAYBACK, mode=PCM_NORMAL, device='default')

## More options for device can be found by executing pcms()

## Default settings for a new PCM object are:

##      * Sample format: PCM_FORMAT_S16_LE
##      * Sample rate: 44100 Hz
##      * Channels: 2
##      * Period size: 32 frames

## For more valid values for these settings and how to change them, see pyalsaaudio documentation

##  pcm_object.read() returns a tuple in the format (number_of_frames, pcm_byte_data)
##  We can reference pcm_byte_data like an integer list. With default settings, size is 128.

def clear_buffer():
    # We clear the recording_pcm buffer so that we are recording the most recent audio
    while recording_pcm.read()[0] != 0:
        print('clearing buffer ...')
    print('buffer cleared')

def record(number_of_periods):
    clear_buffer()
    recording = []
    for i in range(number_of_periods):
        recording.append(recording_pcm.read()[1])
        sleep(0.001) # Not sure why this is a perfect value, but StackOverflow said it would be and it is
    return recording

def playback(recording):
    for period in recording:
        playback_pcm.write(period)

## Analysis

def unsigned_ints_from_pcm_16b_LR(frames):
    # Using default PCM object settings (16-bit little endian)
    left = []
    right = []
    for i in range(0, len(frames), 4):
        left_value = int.from_bytes(frames[i:i+2], 'little') # - int(max_int_16b / 2)     # This value may be off by
        right_value = int.from_bytes(frames[i+2:i+4], 'little') # - int(max_int_16b / 2)  # 0.5, should not matter

        left.append(left_value)
        right.append(right_value)

    return (left, right)

def fill_list_with_zero_complex_part(data):
    # FFT expects real and complex pairs that alternate, e.g. [1, 2] would be considered one value with 1 being the real part
    # and 2(i) being the complex part. We have no need for the complex part, so we fill in zeroes.

    for i in range(len(data)):
        data.insert(i * 2 + 1, 0)

if __name__ == '__main__':
    recording = record(10240)
    print('Pause audio now')
    sleep(3)
    playback(recording)
