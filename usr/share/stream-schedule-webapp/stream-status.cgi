#!/usr/bin/perl
use strict;
use warnings;
use JSON();
use StreamSchedule;

binmode STDOUT, ":encoding(UTF-8)";
print "Content-type: application/json;charset=utf-8\n\n";

StreamSchedule::init();
my $status = getStatus();

my $result = {
    infos    => $status->{messages}->{infos},
    errors   => $status->{messages}->{errors},
    warnings => $status->{messages}->{warnings}
};

for my $num (1 .. 2) {
    my $res = $status->{liquidsoap}->{"station$num"}->{url} || '';
    my $url = $res;
    if ($url =~ /(https?\:\/\/)/) {
        my $protocol = $1;
        my @status   = split(/https?\:\/\//, $url);
        $url = $protocol . $status[-1];
    }
    push @{$result->{channel}},
      {
        status => $res,
        url    => $url
      };
}

if ($result->{"channel"}[0]->{url} =~ /invalid_url/) {
    push @{$result->{errors}}, 'station1 : invalid URL!';
} elsif ($status->{liquidsoap}->{station1}->{error} ne '') {
    push @{$result->{errors}},
      'primary: ' . $status->{liquidsoap}->{station1}->{error};
} elsif ($status->{liquidsoap}->{station2}->{error} ne '') {
    push @{$result->{errors}},
      'fallback: ' . $status->{liquidsoap}->{station2}->{error};
}
print JSON->new()->encode($result);
