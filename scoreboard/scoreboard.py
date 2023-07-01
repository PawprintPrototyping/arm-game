#!/usr/bin/env python
from samplebase import SampleBase
from rgbmatrix import graphics
import time
import random

class GraphicsTest(SampleBase):
    def __init__(self, *args, **kwargs):
        super(GraphicsTest, self).__init__(*args, **kwargs)

    def run(self):
        canvas = self.matrix.CreateFrameCanvas()

        big_font = graphics.Font()
        big_font.LoadFont("fonts/texgyre-27.bdf")

        font = graphics.Font()
        font.LoadFont("fonts/10x20.bdf")

        small_font = graphics.Font()
        small_font.LoadFont("fonts/5x8.bdf")

        red = graphics.Color(255, 0, 0)
        yellow = graphics.Color(255, 255, 0)
        green = graphics.Color(0, 255, 0)
        blue = graphics.Color(0, 0, 255)
        white = graphics.Color(255, 255, 255)
        black = graphics.Color(0, 0, 0)

        message_colors = [yellow, green, blue, white]
        encouraging_message = self.get_encouraging_message()
        encouraging_color = random.choice(message_colors)

        #graphics.DrawLine(canvas, 5, 5, 22, 13, red)
        for minutes in range(0, -1, -1):
            for seconds in range(1, -1, -1):
                if seconds % 7 == 0:
                    encouraging_message = self.get_encouraging_message()
                    encouraging_color = random.choice(message_colors)
                for dsec in range(9, -1, -1):
                    graphics.DrawText(canvas, font, 2, 10, blue, "Text")
                    canvas.Clear()
                    sep = ":"
                    if dsec % 2:
                        sep = " "
                    color = yellow
                    if minutes == 0 and seconds < 30:
                        color = red

                    graphics.DrawText(canvas, font, 1, 25, color, f"{minutes:>2}:{seconds:>02}{'.' if sep == ':' else ' '}{dsec}")
                    graphics.DrawText(canvas, small_font, 75, 22, encouraging_color, encouraging_message)

                    canvas = self.matrix.SwapOnVSync(canvas)
                    time.sleep(0.1)

        #graphics.DrawCircle(canvas, 15, 15, 10, green)

        canvas.Clear()
        canvas.Fill(255, 0, 0)
        graphics.DrawText(canvas, big_font, 12, 25, black, "GAME OVER")
        canvas = self.matrix.SwapOnVSync(canvas)

        time.sleep(10)   # show display for 10 seconds before exit

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
    graphics_test = GraphicsTest()
    if (not graphics_test.process()):
        graphics_test.print_help()
