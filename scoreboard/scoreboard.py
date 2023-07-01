#!/usr/bin/env python
from samplebase import SampleBase
from rgbmatrix import graphics
import time


class GraphicsTest(SampleBase):
    def __init__(self, *args, **kwargs):
        super(GraphicsTest, self).__init__(*args, **kwargs)

    def run(self):
        canvas = self.matrix.CreateFrameCanvas()

        font = graphics.Font()
        font.LoadFont("fonts/10x20.bdf")

        red = graphics.Color(255, 0, 0)
        yellow = graphics.Color(255, 255, 0)
        green = graphics.Color(0, 255, 0)
        blue = graphics.Color(0, 0, 255)
        #graphics.DrawLine(canvas, 5, 5, 22, 13, red)
        for minutes in range(0, -1, -1):
            for seconds in range(59, -1, -1):
                for dsec in range(9, -1, -1):
                    canvas.Clear()
                    sep = ":"
                    if dsec % 2:
                        sep = " "
                    color = yellow
                    if minutes == 0 and seconds < 30:
                        color = red

                    graphics.DrawText(canvas, font, 10, 25, color, f"{minutes:>2}:{seconds:>02}{'.' if sep == ':' else ' '}{dsec}")
                    canvas = self.matrix.SwapOnVSync(canvas)
                    time.sleep(0.1)

        #graphics.DrawCircle(canvas, 15, 15, 10, green)

        graphics.DrawText(canvas, font, 2, 10, blue, "Text")

        time.sleep(10)   # show display for 10 seconds before exit


# Main function
if __name__ == "__main__":
    graphics_test = GraphicsTest()
    if (not graphics_test.process()):
        graphics_test.print_help()
