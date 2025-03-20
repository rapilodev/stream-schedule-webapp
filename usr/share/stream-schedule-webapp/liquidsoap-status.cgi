#!/usr/bin/perl
use strict;
use warnings;
use StreamSchedule;

binmode STDOUT, ":encoding(UTF-8)";
print "Content-type: text/html;charset=utf-8\n\n";

StreamSchedule::init();
my $status = getStatus();

sub station_row {
    my ($name, $key) = @_;
    my $entry = $status->{liquidsoap}->{$key} || {};
    my $url   = $entry->{url} // '';
    my $label = $url;

    $url = $1 . (split(/https?:\/\//, $url))[-1] if $url =~ /(https?:\/\/)/;
    (my $status, $url) = split /\s/, $label, 2;
    $status =~
      s!(connected)!<span class="pin" style="background:green">$1</span>!;
    $status =~ s!(stopped)!<span class="pin" style="background:red">$1</span>!;
    $status =~
      s!(polling)!<span class="pin" style="background:yellow">$1</span>!;

    if ($label =~ /invalid_url/) {
        printInfo("$key : invalid URL!");
    } elsif (my $err = $entry->{error}) {
        printInfo("$name: $err");
    }
    return row [td({class => "label"},$name), td($status), td({class => "grow"}, formatUrl($url))]
      ;
}

print div(
    title("Status"),
    table(
        station_row('primary',  'station1'),
        station_row('fallback', 'station2')
    )
);
