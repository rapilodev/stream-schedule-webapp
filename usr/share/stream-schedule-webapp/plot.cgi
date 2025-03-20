#!/usr/bin/perl
use strict;
use warnings;
use POSIX qw(strftime);

binmode STDOUT, ":encoding(UTF-8)";
print "Content-type: text/html;charset=utf-8\n\n";

our $date = strftime("%Y-%m-%d", localtime);
my $imageUrl  = "/stream-schedule-plot/monitor-$date.svg";
my $imageFile = "/var/log/stream-schedule/plot/monitor-$date.svg";
return unless $imageFile;
print qq{
<h3>Audio Levels</h3>
<a href="$imageUrl" id="plot"><img src="$imageUrl" width="100%" title="target peak=-3dB, target loudness=-20dB RMS"></a>
} . "\n";
