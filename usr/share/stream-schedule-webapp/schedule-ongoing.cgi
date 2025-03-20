#!/usr/bin/perl

use strict;
use warnings;
use feature 'state';
use POSIX qw(strftime);
use StreamSchedule;

binmode STDOUT, ":encoding(UTF-8)";
print "Content-type: text/html;charset=utf-8\n\n";

StreamSchedule::init();
my $status  = getStatus();
my $entry   = $status->{current};
my $title   = 'Ongoing';
my $station = $entry->{station};
my $url1    = $station->{url1};
my $url2    = $station->{url2};
(my $status1, my $status2) = checkUrls($url1, $url2);
print div(
    title($title),
    table(
        row(
            td({class => "label"}, "Date"),
            td({class => "grow"},  $entry->{date})
        ),
        row(
            td({class => "label"}, "Name"),
            td({class => "grow"},  $station->{title})
        ),
        row(
            td({class => "label"},         "primary"),
            td({class => "$status1 grow"}, formatUrl($url1))
        ),
        row(td({class => "label"}, "fallback"),
            td({class => "$status2 grow"}, formatUrl($url2)))
    )
);
