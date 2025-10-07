#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from typing import List, Tuple, Dict, Set, Sequence, Union, Optional, Any
from sys import stderr

from defs import HermesDecompiler, DecompiledFunctionBody, Environment, TokenString, ForInLoopInit, ForInLoopNextIter, RawToken, ReturnDirective, ThrowDirective, JumpNotCondition, JumpCondition, AssignmentToken, BasicBlock, LeftParenthesisToken, RightHandRegToken,  RightParenthesisToken, LeftHandRegToken, NewInnerEnvironmentToken, NewEnvironmentToken, StoreToEnvironment, GetEnvironmentToken, LoadFromEnvironmentToken, FunctionTableIndex

# Implementation for the "NameNonLocalClosureVariables" algorithm (see the .odt notes)

"""
    NOTES about the original Hermes `lib/VM/Interpreter.cpp` file
    handling instructions such as `GetEnvironment`, `CreateEnvironment`,
    `StoreToEnvironment`, `LoadFromEnvironment`:
        - "FRAME.getCalleeClosureUnsafe()->getEnvironment(runtime)"
            ^ This seems to fetch the operand 2 of Call* calls
            containing a closure reference for the current function
        - "curEnv->getParentEnvironment(runtime)"
            ^ This fetches the environement that was to the current
            function's passed-environment at the point of creating
            `curEnv` (through indirecting a linked list), or likely
            the caller's environment
"""

def pass4_name_closure_vars(state : HermesDecompiler, function_body : DecompiledFunctionBody):

    AT = AssignmentToken

    TS = TokenString
    RT = RawToken
    LHRT = LeftHandRegToken
    RHRT = RightHandRegToken

    function_body.local_items : Dict[int, Environment] = {}
    
    parent_environment = function_body.parent_environment

    lines = function_body.statements
    for index, line in enumerate(lines):
        for token in line.tokens:

            if isinstance(token, NewEnvironmentToken):
            
                function_body.local_items[token.register] = Environment(parent_environment, (parent_environment.nesting_quantity + 1) if parent_environment else 0, {})
                line.tokens = [] # Silence this instruction in the produced decompiled code

            elif isinstance(token, NewInnerEnvironmentToken):

                outer_environment = function_body.local_items[token.parent_register]
                function_body.local_items[token.dest_register] = Environment(outer_environment, (outer_environment.nesting_quantity + 1), {})

            elif isinstance(token, GetEnvironmentToken):

                environment = parent_environment
                for nesting in range(token.nesting_level):
                    environment = environment.parent_environment
                
                function_body.local_items[token.register] = environment
                line.tokens = [] # Silence this instruction in the produced decompiled code
    
            elif isinstance(token, FunctionTableIndex):

                if token.environment_id is not None:
                    token.parent_environment = function_body.local_items[token.environment_id]

            elif isinstance(token, StoreToEnvironment):
                varname = '_closure%d_slot%d' % (function_body.local_items[token.env_register].nesting_quantity,
                    token.slot_index)
                
                if token.slot_index not in function_body.local_items[token.env_register].slot_index_to_varname:
                    function_body.local_items[token.env_register].slot_index_to_varname[token.slot_index] = varname
                    line.tokens = [RT('var ' + varname), AT(), RHRT(token.value_register)]
                
                else: # This a closure-referenced variable reassignment
                    line.tokens = [RT(varname), AT(), RHRT(token.value_register)]
               
            elif isinstance(token, LoadFromEnvironmentToken):
                # Resolve which attribute carries the environment register across versions
                env_reg = None
                for attr in ("env_register", "environment_register", "environment_id"):
                    if hasattr(token, attr):
                        env_reg = getattr(token, attr)
                        break
                # Fallback: some builds store the env reg in `register`
                if env_reg is None and hasattr(token, "register"):
                    env_reg = token.register

                env = function_body.local_items.get(env_reg)
                if env is None:
                    # Last-resort fallback so we don't crash; names will still be stable
                     env = parent_environment

                nesting = env.nesting_quantity if env is not None else 0
                var_name = '_closure%d_slot%d' % (nesting, token.slot_index)

    # Replace the RHS with the named closure variable.
    # In all supported IRs, the RHS is at index 2 for this pass.
    # line.tokens[2] = RT(var_name)

    #        elif isinstance(token, LoadFromEnvironmentToken):
    #            # Use the environment register, not the destination register.
    #           env = function_body.local_items.get(token.env_register)
    #            if env is None:
    #                raise KeyError(f"Unknown environment register r{token.env_register} in LoadFromEnvironmentToken")
    #            var_name = '_closure%d_slot%d' % (env.nesting_quantity, token.slot_index)
    #            # Replace RHS with the named closure variable
    #            line.tokens[2] = RT(var_name)
