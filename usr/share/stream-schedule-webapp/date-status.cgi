#!/usr/bin/perl
use strict;
use warnings;
use POSIX qw(strftime);
use StreamSchedule;

binmode STDOUT, ":encoding(UTF-8)";
print "Content-type: text/html;charset=utf-8\n\n";

StreamSchedule::init();
my $status = getStatus();
print div (
    title("Date"),
    table(
        row(
            td({class => "label"},            "date"),
            td(formatDateSec($status->{now}), {class => "date"})
        ),
        row(
            td({class => "label"},                  "last status update"),
            td(formatDateSec($status->{statusAge}), {class => "date"})
        ),
        row(
            td({class => "label"},                    "last schedule update"),
            td(formatDateSec($status->{scheduleAge}), {class => "date"})
        ),
    )
);
