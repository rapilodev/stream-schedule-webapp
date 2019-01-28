#!/usr/bin/perl

use warnings;
use strict;

use JSON;
use File::ReadBackwards();

my $allowUrl='https://fr-bb.org';

my ($sec,$min,$hour,$day,$month,$year) = localtime(time);
my $today = sprintf("%04d-%02d-%02d", $year+1900, $month+1, $day, $hour, $min, $sec);

my $path = "/var/log/stream-schedule/plot/monitor-$today.log";
my $backwards = File::ReadBackwards->new( $path ) or die ("cannot read data file");
my $line = $backwards->readline;
chomp $line;

my ( $datetime, $rmsLeftIn, $rmsRightIn, $peakLeftIn, $peakRightIn, $rmsLeftOut, $rmsRightOut, $peakLeftOut, $peakRightOut ) = split( /\t/, $line );

my $content=qq{Access-Control-Allow-Origin: $allowUrl\n};
$content .=qq{Content-type:application/json; charset=utf-8\n\n};

my $data={
	datetime => $datetime,
	in => {
		rmsLeft => $rmsLeftIn,
		rmsRight => $rmsRightIn,
		peakLeft => $peakLeftIn,
		peakRight => $peakRightIn
	},
	out => {
		rmsLeft => $rmsLeftOut,
		rmsRight => $rmsRightOut,
		peakLeft => $peakLeftOut,
		peakRight => $peakRightOut
	}
};

$content.= encode_json($data);
print $content;

