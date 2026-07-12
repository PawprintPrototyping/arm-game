// Spacer to mount targets to side fumblers, robot, and flappy-doos

$fn = 100;

module spacer(id, od, length) {
    difference() {
        cylinder(h=length, r=od/2);
        cylinder(h=length, r=id/2);
    }
}

spacer(id=6.4, od=12.5, length=18);