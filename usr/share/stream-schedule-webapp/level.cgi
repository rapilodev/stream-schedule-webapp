#!/usr/bin/perl
use warnings;
use strict;
use JSON;
use File::ReadBackwards();

print join "\n",
  (
    q{Access-Control-Allow-Origin: *},
    q{Content-type:application/json; charset=utf-8},
    "\n"
  );

my ($sec, $min, $hour, $day, $month, $year) = localtime(time);
my $today = sprintf("%04d-%02d-%02d", $year + 1900, $month + 1, $day);

my $path      = "/var/log/stream-schedule/plot/monitor-$today.log";
my $backwards = File::ReadBackwards->new($path)
  or (print(encode_json {msg => "cannot read data file"}) && exit);
my $line = $backwards->readline;
chomp $line;

my (
    $datetime,   $rmsLeftIn,   $rmsRightIn,  $peakLeftIn, $peakRightIn,
    $rmsLeftOut, $rmsRightOut, $peakLeftOut, $peakRightOut
) = split(/\t/, $line);

print encode_json {
    datetime => $datetime,
    in       => {
        rmsLeft   => $rmsLeftIn,
        rmsRight  => $rmsRightIn,
        peakLeft  => $peakLeftIn,
        peakRight => $peakRightIn
    },
    out => {
        rmsLeft   => $rmsLeftOut,
        rmsRight  => $rmsRightOut,
        peakLeft  => $peakLeftOut,
        peakRight => $peakRightOut
    }
};

