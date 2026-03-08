local stdnse    = require "stdnse"
local shortport = require "shortport"
local tn3270    = require "tn3270"
local brute     = require "brute"
local creds     = require "creds"
local unpwdb    = require "unpwdb"
local nmap = require "nmap"
local string = require "string"
local stringaux = require "stringaux"

description = [[
TPX User ID enumerator for IBM mainframes (z/OS). The TPX logon panel
tells you when a user ID is valid or invalid with the message:
 <code>IKJ56420I Userid <user ID> not authorized to use TPX</code>.

The TPX logon process can work in two ways:
1) You get prompted with <code>IKJ56700A ENTER USERID -</code>
   to which you reply with the user you want to use.
   If the user ID is valid it will give you a normal
   TPX logon screen. Otherwise it will give you the
   screen logon error above.
2) You're given the TPX logon panel and enter your user ID
   at the <code>Userid    ===></code> prompt. If you give
   it an invalid user ID you receive the error message above.

This script relies on the NSE TN3270 library which emulates a
TN3270 screen for NMAP.

TPX user IDs have the following rules:
 - it cannot begin with a number
 - only contains alpha-numeric characters and @, #, $.
 - it cannot be longer than 7 chars
]]

---
-- @args tpx-enum.commands Commands in a semi-colon separated list needed
-- to access TPX. Defaults to <code>tpx</code>.
--
-- @usage
-- nmap --script=tpx-enum -p 23 <targets>
--
-- @usage
-- nmap -sV -p 9923 10.32.70.10 --script tpx-enum --script-args userdb=tpx_users.txt,tpx-enum.commands="logon applid(tpx)"
--
-- @output
-- PORT   STATE SERVICE VERSION
-- 23/tcp open  tn3270  IBM Telnet TN3270
-- | tpx-enum:
-- |   TPX User ID:
-- |     TPX User:RAZOR -  Valid User ID
-- |     TPX User:BLADE -  Valid User ID
-- |     TPX User:PLAGUE -  Valid User ID
-- |_  Statistics: Performed 6 guesses in 3 seconds, average tps: 2
--
-- @changelog
-- 2015-07-04 - v0.1 - created by Soldier of Fortran
-- 2015-10-30 - v0.2 - streamlined the code, relying on brute and unpwdb and
--                     renamed to tpx-enum.
-- 2017-1-13  - v0.3 - Fixed 'data' bug and added options checking to speedup
-- 2019-02-01 - v0.4 - Disabled TN3270 Enhanced support and fixed debug errors


author = "Philip Young aka Soldier of Fortran"
license = "Same as Nmap--See https://nmap.org/book/man-legal.html"
categories = {"intrusive", "brute"}

portrule = shortport.port_or_service({23,992,623,2323,3270,3271,3272,3273,3274,3275}, {"tn3270"})

Driver = {
  new = function(self, host, port, options)
    local o = {}
    setmetatable(o, self)
    self.__index = self
    o.host = host
    o.port = port
    o.options = options
    o.tn3270 = tn3270.Telnet:new()
    o.tn3270:disable_tn3270e()
    return o
  end,
  connect = function( self )
    local status, err = self.tn3270:initiate(self.host,self.port)
    self.tn3270:get_screen_debug(2)
    if not status then
      stdnse.debug("Could not initiate TN3270: %s", err )
      return false
    end
    return true
  end,
  disconnect = function( self )
    self.tn3270:send_pf(3)
    self.tn3270:disconnect()
    self.tn3270 = nil
    return true
  end,
  login = function (self, user, pass)
  -- pass is actually the user id we want to try
    local commands = self.options['key1']
    local skip = self.options['skip']
    stdnse.debug(2,"Getting to TPX")
    local run = stringaux.strsplit(";%s*", commands)
    for i = 1, #run do
      stdnse.debug(2,"Issuing Command (#%s of %s): %s", i, #run ,run[i])
      if i == #run and run[i]:upper():find("LOGON APPLID") and skip then
        stdnse.verbose(2,"Trying User ID: %s", pass)
        self.tn3270:send_cursor(run[i] .. " DATA(" .. pass .. ")")
      elseif i == #run and skip then
        stdnse.verbose(2,"Trying User ID: %s", pass)
        self.tn3270:send_cursor(run[i] .. " " .. pass)
      else
        self.tn3270:send_cursor(run[i])
      end
      self.tn3270:get_all_data()
    end

    if not self.tn3270:find("Userid:")
       and not self.tn3270:find("Password:")
       and not self.tn3270:find("ACF01004 LOGONID")
       and not self.tn3270:find("MSGID:")
       and not self.tn3270:find("NO USER APPLID AVAILABLE")
       or self.tn3270:isClear() then
      local err = brute.Error:new("Too many connections")
        -- This error occurs on too many concurrent application requests it
        -- should be temporary. We use the new setReduce function here to reduce number of connections.
      err:setReduce(true)
      stdnse.debug(1,"TPX Unavailable at the moment - UserID %s - Not at a TPX screen", pass )
      return false, err
    end

    if not skip then
      stdnse.verbose(2,"Trying User ID: %s", pass)
      self.tn3270:send_cursor(pass)
      self.tn3270:get_all_data()
      -- some systems require an enter after sending a valid user ID
    end

    stdnse.debug(2,"Screen Received for User ID: %s", pass)
    self.tn3270:get_screen_debug(2)
    if self.tn3270:find('ACF01004 LOGONID') then -- invalid user ID
      return false,  brute.Error:new( "Invalid User ID" )
    elseif self.tn3270:find('MSGID:') then
      stdnse.verbose("Valid TPX User ID: %s - MSGID", string.upper(pass))
      return true, creds.Account:new("TPX User",string.upper(pass), " Valid User ID - MSGID")
    else
      stdnse.verbose("Valid TPX User ID: %s", string.upper(pass))
      return true, creds.Account:new("TPX User",string.upper(pass), " Valid User ID")
    end
  end
}

--- Tests the target to see if we can even get to TPX
--
-- @param host host NSE object
-- @param port port NSE object
-- @param commands script-args of commands to use to get to TPX
-- @return status true on success, false on failure
-- @return name of security product installed
local function tpx_test( host, port, commands )
  stdnse.debug("Checking for TPX")
  local tn = tn3270.Telnet:new()
  tn:disable_tn3270e()
  local status, err = tn:initiate(host,port)
  local tpx = false -- initially we're not at TPX logon panel
  local secprod = "RACF"
  tn:get_screen_debug(2) -- prints TN3270 screen to debug
  if not status then
    stdnse.debug("Could not initiate TN3270: %s", err )
    return tpx, "Could not Initiate TN3270"
  end
  local run = stringaux.strsplit(";%s*", commands)
  for i = 1, #run do
    stdnse.debug(2,"Issuing Command (#%s of %s): %s", i, #run ,run[i])
    tn:send_cursor(run[i])
    tn:get_all_data()
  end
  tn:get_screen_debug(2)

  if tn:find("***") then
    secprod = "TopSecret/ACF2"
  end

  if tn:find("Userid:") or tn:find("Password:")  then
    tpx = true
    -- We're probably (like 99% sure) in TPX
    tn:send_cursor("notreal")
    tn:get_all_data()
    if tn:find("ACF01004") then
      secprod = 'ACF2'
    end
  end
  tn:send_pf(3)
  tn:disconnect()
  return tpx, secprod, "Could not get to TPX. Try --script-args=tpx-enum.commands='logon applid(tpx)'. Aborting."
end

--- Tests the target to see if we can speed up brute forcing
-- VTAM/USSTable will sometimes allow you to put the userid
-- in the command area either through data() or just adding
-- the userid. This function will test for both
--
-- @param host host NSE object
-- @param port port NSE object
-- @param commands script-args of commands to use to get to TPX
-- @return status true on success, false on failure
local function tpx_skip( host, port, commands )
  stdnse.debug("Checking for IKJ56700A message skip")
  local tn = tn3270.Telnet:new()
  tn:disable_tn3270e()
  stdnse.debug2("Connecting TN3270 to %s:%s", host.targetname or host.ip, port.number)
  local status, err = tn:initiate(host,port)
  stdnse.debug2("Displaying initial TN3270 Screen:")
  tn:get_screen_debug(2) -- prints TN3270 screen to debug
  if not status then
    stdnse.debug("Could not initiate TN3270: %s", err )
    return false
  end
  -- We're connected now to test.
  local data = false
  if commands:upper():find('LOGON APPLID') then
    stdnse.debug(2,"Using LOGON command (%s) trying DATA() command", commands )
    data = true
  else
    stdnse.debug(2,"Not using LOGON command, testing adding userid to command" )
  end

  local run = stringaux.strsplit(";%s*", commands)
  for i = 1, #run do
    stdnse.debug(2,"Issuing Command (#%s of %s): %s", i, #run ,run[i])
    if i == #run then
      if data then
        stdnse.debug(2,"Sending "..run[i].." DATA(FAKEUSER)")
        tn:send_cursor(run[i].." DATA(FAKEUSER)")
      else
        stdnse.debug(2,"Sending "..run[i].." FAKEUSER")
        tn:send_cursor(run[i].." FAKEUSER")
      end
    else
      tn:send_cursor(run[i])
    end
    tn:get_all_data()
  end
  tn:get_screen_debug(2)

  if tn:find("ACF01004 LOGONID")   then
    stdnse.debug('Accelrator skip supported')
    return true
  else
    return false
  end
end


-- Filter iterator for unpwdb
-- TPX is limited to 7 alpha numeric and @, #, $ and can't start with a number
-- pattern:
--  ^%D     = The first char must NOT be a digit
-- [%w@#%$] = All letters including the special chars @, #, and $.
local valid_name = function(x)
  return (string.len(x) <= 7 and string.match(x,"^%D+[%w@#%$]"))
end

-- Iterator that first yields default users, then filtered unpwdb users
local combined_username_iterator = function()
  local default_users = {'TPXADMIN', 'TPXOPER', 'NVIADMIN','STXADMIN','STXOPER'}
  local default_index = 1
  local unpwdb_iter = unpwdb.filter_iterator(brute.usernames_iterator(), valid_name)
  
  return function()
    -- First, yield default users
    if default_index <= #default_users then
      local user = default_users[default_index]
      default_index = default_index + 1
      return user
    end
    
    -- Then yield from unpwdb iterator
    return unpwdb_iter()
  end
end

action = function(host, port)
  local commands = stdnse.get_script_args(SCRIPT_NAME .. '.commands') or "tpx"
  local tpxtst, secprod, err = tpx_test(host, port, commands)
  if tpxtst then
    local options = { key1 = commands, skip = tpx_skip(host, port, commands) }
    stdnse.debug("Starting TPX User ID Enumeration")
    local engine = brute.Engine:new(Driver, host, port, options)
    engine.options.script_name = SCRIPT_NAME
    engine:setPasswordIterator(combined_username_iterator(),valid_name)
    engine.options.passonly = true
    engine.options:setTitle("TPX Users")
    local status, result = engine:start()
    -- port.version.extrainfo = "Security: " .. secprod
    nmap.set_port_version(host, port)
    return result
  else
    return err
  end

end
