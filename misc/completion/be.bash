#!/bin/bash
# Bash completion script for be (Bugs Everywhere)
#
# System wide installation:
#   Copy this file to /etc/bash_completion/be
# Per-user installation:
#   Copy this file to ~/.be-completion.sh and source it in your .bashrc:
#     source ~/.be-completion.sh
# 
# For a good intro to Bash completion, see Steve Kemp's article
#   "An introduction to bash completion: part 2"
#   http://www.debian-administration.org/articles/317

# Requires:
#   be [X Y Z] --complete
#       to print a list of available completions at that point
_be()
{
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    
    if [ $COMP_CWORD -eq 1 ]; then
	# no command yet, show all commands
	COMPREPLY=( $( compgen -W "$(be --complete)" -- $cur ) )
    else
	# remove the first word (should be "be") for security reasons
	unset COMP_WORDS[0]
	# remove the current word and all later words, because they
	# are not needed for completion.
	for i in `seq $COMP_CWORD ${#COMP_WORDS[@]}`; do
	    unset COMP_WORDS[$i];
	done
	COMPREPLY=( $( IFS=$'\n' compgen -W "$(be "${COMP_WORDS[@]}" --complete $cur)" -- $cur ) )
    fi
}

complete -F _be be
