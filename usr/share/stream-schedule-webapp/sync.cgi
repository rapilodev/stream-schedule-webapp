#!/usr/bin/perl
use strict;
use warnings;
use StreamSchedule;

binmode STDOUT, ":encoding(UTF-8)";
print "Content-type: text/html;charset=utf-8\n\n";

StreamSchedule::init();
saveFile('scheduler/triggerSyncFile',
    $StreamSchedule::syncTriggerFile, '');
printInfo("synchronization initiated");
