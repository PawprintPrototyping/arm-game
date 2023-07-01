#!/usr/bin/env python
import os
import threading

DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

from rgbbase import RGBBase
if DEBUG:
    from RGBMatrixEmulator import graphics
else:
    from rgbmatrix import graphics

import time
import random

class Scoreboard(RGBBase):
    def __init__(self, *args, **kwargs):
        super(Scoreboard, self).__init__(*args, **kwargs)

        self.minutes = kwargs.get("minutes", 1)
        self.seconds = kwargs.get("seconds", 0)
        self.stop = False
        self.pause = False
        self.delay_thread = threading.Thread()

        self.black = graphics.Color(0, 0, 0)
        self.big_font = graphics.Font()
        self.big_font.LoadFont("fonts/texgyre-27.bdf")

        self.font = graphics.Font()
        self.font.LoadFont("fonts/10x20.bdf")

        self.small_font = graphics.Font()
        self.small_font.LoadFont("fonts/5x8.bdf")

    def run(self, timer_minutes=None, timer_seconds=None):
        if timer_minutes is None:
            timer_minutes = self.minutes
        if timer_seconds is None:
            timer_seconds = self.seconds
        canvas = self.matrix.CreateFrameCanvas()

        red = graphics.Color(255, 0, 0)
        yellow = graphics.Color(255, 255, 0)
        green = graphics.Color(0, 255, 0)
        blue = graphics.Color(0, 0, 255)
        white = graphics.Color(255, 255, 255)

        message_colors = [yellow, green, blue, white]
        encouraging_message = self.get_encouraging_message()
        encouraging_color = random.choice(message_colors)

        #graphics.DrawLine(canvas, 5, 5, 22, 13, red)
        for minutes in range(timer_minutes-1, -1, -1):
            for seconds in range(timer_seconds-1, -1, -1):
                if seconds % 7 == 0:
                    encouraging_message = self.get_encouraging_message()
                    encouraging_color = random.choice(message_colors)
                for dsec in range(9, -1, -1):
                    canvas.Clear()
                    sep = ":"
                    if dsec % 2:
                        sep = " "
                    color = yellow
                    if minutes == 0 and seconds < 30:
                        color = red

                    graphics.DrawText(canvas, self.font, 1, 25, color, f"{minutes:>2}:{seconds:>02}{'.' if sep == ':' else ' '}{dsec}")
                    graphics.DrawText(canvas, self.small_font, 75, 22, encouraging_color, encouraging_message)

                    canvas = self.matrix.SwapOnVSync(canvas)
                    time.sleep(0.1)
                    if self.stop:
                        return
                    while self.pause:
                        time.sleep(0.1)

        #graphics.DrawCircle(canvas, 15, 15, 10, green)

        time.sleep(10)   # show display for 10 seconds before exit

    def game_over(self, blocking=False):
        canvas = self.matrix.CreateFrameCanvas()
        canvas.Clear()
        canvas.Fill(255, 0, 0)
        graphics.DrawText(canvas, self.big_font, 12, 25, self.black, "GAME OVER")
        self.matrix.SwapOnVSync(canvas)
        if blocking:
            while not self.stop:
                time.sleep(0.1)


    def get_encouraging_message(self):
        potential_messages = [
          "You're doing good!",
          "Shoot that robot!",
          "Seeya, space cowboy",
          "[Encouraging Message 4]",
          "Sharp shootin', Tex"
        ]
        return random.choice(potential_messages)
        

# Main function
if __name__ == "__main__":
    graphics_test = Scoreboard()
    if (not graphics_test.process()):
        graphics_test.print_help()
