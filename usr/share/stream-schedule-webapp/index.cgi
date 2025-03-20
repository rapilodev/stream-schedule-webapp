#!/usr/bin/perl
use strict;
use warnings;
use StreamSchedule;

binmode STDOUT, ":encoding(UTF-8)";
print "Content-type: text/html;charset=utf-8\n\n";

StreamSchedule::init();
printHeader();
my $status = getStatus();

print join'',(
    qq{<div id="messages"></div>},
    q{<div id="content">},
        qq{<div class="panel" id="date-status"></div>},
        qq{<div class="panel" id="liquidsoap-status"></div>},
        qq{<div class="panel" id="schedule-ongoing"></div>},
        qq{<div class="panel" id="schedule-upcoming"></div>},
        qq{<div class="panel" id="audio-levels" class="panel"></div>},
        qq{<div class="panel" id="plot"></div>},
        qq{<div class="panel" id="schedule"></div>},
    qq{</div></body></html>}
);
